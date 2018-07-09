#!/usr/bin/python3.5

class Main(object):
	"""
	Main program module, handles setting up the environment,
	handling arguments and running other modules in this 
	program
	"""
	def __init__(self):
		self.handleImports()

		self.useregex = False
		self.ignoreCase = False
		self.verbose = False

		args = self.addArguments()
		self.invokeMain(args)

	def handleImports(self):
		"""
		Import required packages or fail
		"""
		packages = ['sqlite3', 're', 'sys', 'argparse', 'tempfile', 'shutil', 'os', 'zipfile', 'colorama']
		missingPackages = []

		for p in packages:
			try:
				lib = __import__(p)
				globals()[p] = lib
			except Exception as e:
				print(e)
				missingPackages.append(p)

		colorama.init()

		if len(missingPackages) > 0:
			print("The following packages are required (Consider using `pip install` tool):")
			print("\t" + ", ".join(missingPackages))
			exit(1)

	def addArguments(self):
		"""
		Create an argument parser object with the available arguments
		@return ArgumentParser object with parsed arguments
		"""
		parser = argparse.ArgumentParser(description="Replace specific items in an EasyWorship Schedule File (.EWSX)")
		parser.add_argument("inputfile", metavar='input', type=str, help="The schedule to update")
		parser.add_argument("outputfile", metavar="output", type=str, help="The desired name of the output schedule", default="output.ewsx")
		parser.add_argument("search", metavar="search", type=type(r''), help="The string to replace in the schedule")
		parser.add_argument("replace", metavar="replace", type=type(r''), help="The string to replace the search string with in the schedule")
		parser.add_argument("-r", "--regex", help="Treat search and replace strings as regular expressions, including usage of groups", action="store_true")
		parser.add_argument("-i", "--ignore-case", help="Ignore case in search string", action="store_true")
		parser.add_argument("-d", "--dry-run", help="Print updated values instead of writing directly to database. Useful for finding the right search and replace strings", action="store_true")
		return parser.parse_args()

	def invokeMain(self, args):
		"""
		Invoke the main flow according to specifications in command line arguments
		@param args 	ArgumentParser object
		"""
		if not os.path.isfile(args.inputfile):
			print("{0}: File {1} could not be found".format(bcolors.fail("ERROR"), bcolors.okblue(args.inputfile)))
			exit(2)
		if not args.inputfile.endswith('.ewsx'):
			print("Input file does not have the proper extension to be an EasyWorship schedule file. Exiting")
			exit(3)

		extractor = ScheduleExtractor(args.inputfile, args.outputfile, args.dry_run)

		if not args.dry_run and extractor.checkTargetExists():
			print("The specified output file {0} alreadd exists and will be overridden".format(bcolors.okblue(args.outputfile)))
			user_response = input("Do you wish to continue? (Y/n)\n")
			yesChoice = ['yes', 'Yes', 'YES', 'Y']
			noChoice = ['n', 'N', 'NO', 'no', 'No']
			while user_response not in yesChoice + noChoice:
				print("Please choose Y(es) or n(o). This input is case sensitive")
				user_response = input("Do you wish to continue? (Y/n)\n")

			if user_response in noChoice:
				exit(0)

		database_location = extractor.extractSchedule()
		ewdbr = EWDatabaseRewriter(args.search, args.replace, args.regex, args.dry_run, args.ignore_case, os.path.join(database_location, 'main.db'))
		if not args.dry_run:
			extractor.zipResults()
		extractor.cleanup()

		print(bcolors.okgreen("Done!"))

		if not args.dry_run:
			print("The updated file can be found in", bcolors.okblue(extractor.getOutputFile()))

class EWDatabaseRewriter(object):
	"""
	Object for replacing the specified strings in the database 
	inside the EasyWorship Schedule file (.ewsx) 
	"""

	def __init__(
		self, 
		search, 
		replace, 
		useregex = False, 
		dryRun = False, 
		ignoreCase = True, 
		database = 'main.db'
	):
		"""
		@param search 		Input string to search for
		@param replace 		Output string to replace input with
		@param useregex 	Input and output strings are regex instead of plain string
		@param verbose 		Print output to standard out
		@param dryRun 		Do not actually update database, but show changes instead
		@param ignorecase 	Ignore case while searching for search string
		@param database		Name of the database file
		"""
		self.conn = sqlite3.connect(database)
		self.c = self.conn.cursor()
		self.dryRun = dryRun
		self.replacewith = replace
		self.ignorecase = ignoreCase

		if useregex:
			self.searchValue = self.searchValueRegex
			self.printDifference = self.printDifferenceRegex
			self.substituteValue = self.substituteValueRegex
			if self.ignorecase:
				self.input = re.compile(search, re.IGNORECASE)
			else:
				self.input = re.compile(search)
		else:
			self.searchValue = self.searchValuePlain
			self.printDifference = self.printDifferencePlain
			self.substituteValue = self.substituteValuePlain
			self.input = search

		self.runReplacement()

	def runReplacement(self):
		"""
		Default flow for this class. Run the replacement function only on those tables and
		columns that contain the specified search string
		"""
		tables = self.getTables()
		tables_with_string, found_occurences = self.getTablesWhereStringExists(tables, self.input)
		if found_occurences > 0:
			self.startReplacement(tables_with_string, self.input, self.replacewith, found_occurences)
		else:
			print("Nothing to do here")
		
		self.c.close()
		self.conn.close()

	def getTables(self):
		"""
		Get a list of all tables in the database
		@return List of table names
		"""
		result = self.c.execute("select name from sqlite_master where type = 'table'")
		return [t[0] for t in result]

	def getTablesWhereStringExists(self, tables, search):
		"""
		Check which tables contain the string to replace
		@return Dictionary of table names as keys and list of column names as values
			of tables and columns where search string occurs
		"""
		tables_with_string = dict()
		total_occurences = 0.0

		for t in tables:
			res = self.c.execute("select * from " + t)
			names = list(map(lambda x: x[0], self.c.description))
			for r in res:
				for i, cell in enumerate(list(r)):
					if isinstance(cell, str):
						if self.searchValue(search, cell):
							try:
								if names[i] not in tables_with_string[t]:
									tables_with_string[t].append(names[i])
							except:
								tables_with_string[t] = [names[i]]
							total_occurences += 1

		print("Found %i occurences in %s tables:" % (total_occurences, len(tables_with_string)))
		
		for t in tables_with_string:
			print("\t{0} ({1} columns where string occurs: {2})".format(t, len(tables_with_string[t]), ", ".join(tables_with_string[t])))

		return tables_with_string, total_occurences

	def startReplacement(self, tables, search, replace, expectedTotal):
		"""
		Update the database by replacing all occurences or the search string
		for the replacement string, or only print the expected difference if
		the dry run is enabled
		@param tables 		Dictionary of tables where the search string occurs
							as key and a list of columns within that table where
							the search string occurs as value
		@param search 		The string to replace within the database
		@param replace 		The replacement for search
		@param expectedTotal The number of entries to update (used for progress).
		"""
		replaced_count = 0.0

		if not self.dryRun:
			print("Starting replacing in database")
			print("")

		for t in tables.keys():
			for col in tables[t]:
				result = self.c.execute('select rowid, {0} from {1}'.format(col, t))
				c2 = self.conn.cursor()
				for r in result:
					value = r[1]
					if self.searchValue(search, value):
						replaced_col = self.substituteValue(search, replace, value)
						if self.dryRun:
							self.printDifference(search, replace, value, replaced_col)
						else:
							query = "update `{0}` set `{1}`=? where `rowid`=?".format(t, col)
							c2.execute(query, (replaced_col, r[0]))
							if (replaced_count % 20 == 0):
								sys.stdout.write("\r%i%%                " % (replaced_count / expectedTotal * 100.0))
								sys.stdout.flush()
						replaced_count += 1
				if not self.dryRun:
					self.conn.commit()
				c2.close()

		print(
			"\r{3}\n{2} {0} items in {1} tables: ".format(
				int(replaced_count), 
				len(tables.keys()), 
				"showed difference of " if self.dryRun else "replaced", 
				bcolors.okgreen("100%")
			)
		)
		for t in tables.keys():
			print("\t{0} (columns: {1})".format(bcolors.okblue(t), ", ".join(map(lambda x: bcolors.okblue(x), tables[t]))))

	def searchValuePlain(self, searchstring, value):
		"""
		Perform a non-regex search on a string
		@param searchstring 	The needle to look for
		@param value 			The haystack
		@return 	Bool if value contains searchstring
		"""
		if self.ignorecase:
			return searchstring.lower() in value.lower()
		else:
			return searchstring in value

	def searchValueRegex(self, searchstring, value):
		"""
		Perform a regex search on a string
		@param searchstring 	The needle to look for
		@param value 			The haystack
		@return 	Bool if value contains searchstring
		"""
		return searchstring.search(value)

	def substituteValuePlain(self, searchstring, replacement, value):
		"""
		Substitute all occurences of the searchstring for the replacement in the 
		given value

		@param searchstring 	The needle to look for
		@param replacement 		The value to replace the searchstring with
		@param value 			The haystack
		@return 	The updated string
		"""
		if self.ignorecase:
			return value.replace(searchstring, replacement)
		else:
			newstr = ""
			lastIndex = 0
			while lastIndex < len(value):
				index = value.lower().find(searchstring.lower(), lastIndex)
				if index < 0:
					newstr += value[lastIndex:]
					lastIndex = len(value)
				else:
					newstr += value[lastIndex:index]
					newstr += replacement
					lastIndex = index + len(searchstring)
			return newstr

	def substituteValueRegex(self, searchstring, replacement, value):
		"""
		Substitute all occurences of the searchstring regex for the replacement 
		in the given value. Make use of groups where required

		@param searchstring 	The needle regex to look for
		@param replacement 		The value to replace the searchstring with
		@param value 			The haystack
		@return 	The updated string
		"""
		return re.sub(searchstring, replacement, value)

	def printDifferencePlain(self, search, replace, value, newValue):
		"""
		Highlight the differences between the input and output of the plain text substitute function
		@param search 	The pattern
		@param replace 	The replacement string as provided to the substitute method
		@param value 	The original input value of the substitute method
		@param newValue The output of the substitute method which took the other 
						three parameters as arguments
		"""
		searchlen = len(search)
		replacelen = len(replace)
		stdDiscrepency = replacelen - searchlen
		original = bcolors.fail('- ')
		new = bcolors.okgreen('+ ')
		lastIndex = 0
		discrepency = 0
		while lastIndex < len(value):
			if self.ignorecase:
				index = value.lower().find(search.lower(), lastIndex) 
			else:
				index = value.find(search, lastIndex)
			print(index, lastIndex)

			if index < 0:
				lastIndex = len(value)
			else:
				original += value[lastIndex:index]
				original += bcolors.fail(value[index:index+searchlen])

				new += newValue[lastIndex+discrepency:index+discrepency]
				new += bcolors.okgreen(replace)

				lastIndex = index + searchlen
				discrepency -= stdDiscrepency

			original += value[lastIndex:]
			new += newValue[lastIndex+discrepency:]

		print(original)
		print(new)
		print("\n")

	def printDifferenceRegex(self, search, replace, value, newValue):
		"""
		Highlight the differences between the input and output of the regex substitute function
		@param search 	The pattern
		@param replace 	The replacement string as provided to the substitute method
		@param value 	The original input value of the substitute method
		@param newValue The output of the substitute method which took the other 
						three parameters as arguments
		"""
		matches = search.finditer(value)
		original = bcolors.fail('- ')
		new = bcolors.okgreen("+ ")
		lastIndex = 0
		discrepency = 0
		for m in matches:
			sublen = len(re.sub(search, replace, value[m.start():m.end()]))

			original += value[lastIndex:m.start()]
			original += bcolors.fail(value[m.start():m.end()])
			
			new += newValue[lastIndex+discrepency:m.start()+discrepency]
			new += bcolors.okgreen(newValue[m.start()+discrepency:m.start()+discrepency+sublen])

			lastIndex = m.end()
			discrepency += sublen - (m.end() - m.start())

		original += value[lastIndex:]
		new += newValue[lastIndex+discrepency:]

		print(original)
		print(new)
		print("\n")

class ScheduleExtractor(object):
	"""
	Class for extracting the contents of an EasyWorship schedule
	file (.ewsx) to a hidden directory on the system, repacking
	the results after manipulation of the database, and cleaning up
	"""

	def __init__(self, i, o, dryRun):
		"""
		Constructor
		@param i 		Input file location
		@param o 		Output file location
		"""
		self.input = i
		self.output = self.getAbsoluteOutPath(o)
		self.writestatus = not dryRun		

	def extractSchedule(self):
		"""
		Extract the EasyWorship Schedule (.ewsx) file to a hidden directory
		on the system
		@return Absolute path to the extracted data on the system
		"""
		self.tempdir = tempfile.mkdtemp()
		self.ziptarget = os.path.abspath(os.path.join(self.tempdir, 'tempschedule.zip'))
		self.zipcontenttarget = os.path.abspath(os.path.join(self.tempdir, 'scheduleContents'))
		shutil.copy(self.input, self.ziptarget)
		zip_ref = zipfile.ZipFile(self.ziptarget, 'r')
		zip_ref.extractall(self.zipcontenttarget)
		zip_ref.close()
		if self.writestatus:
			print(
				"Finished extraction of {0} to {1}".format(
					bcolors.okblue(self.input), 
					bcolors.okblue(self.zipcontenttarget)
				)
			)

		return self.zipcontenttarget

	def zipResults(self):
		"""
		Zip the results of the database replacement and write the results
		to the specified output file
		"""
		zip_ref = zipfile.ZipFile(self.output, 'w', zipfile.ZIP_DEFLATED)
		for dirname, subdirs, files in os.walk(self.zipcontenttarget):
			if dirname is not self.zipcontenttarget:
				zip_ref.write(dirname, os.path.relpath(dirname, self.zipcontenttarget))
			for filename in files:
				realpath = os.path.join(dirname, filename)
				relpath = os.path.relpath(realpath, self.zipcontenttarget)
				zip_ref.write(realpath, relpath)
		zip_ref.close()

	def getAbsoluteOutPath(self, out):
		"""
		Convert the output argument to an absolute path
		@param out 		Argument specified as program output location
		@return The absolute path for the specified output file name
		"""
		if not out.endswith('.ewsx'):
			out += ".ewsx"
		if os.path.isabs(out):
			return out
		else:
			return os.path.abspath(os.path.join(os.getcwd(), out))

	def checkTargetExists(self):
		"""
		Checks if the specified output file already exists
		@return True iff file already exists
		"""
		return os.path.isfile(self.output)

	def cleanup(self):
		"""
		Cleanup all temporary data
		"""
		try:
			shutil.rmtree(self.tempdir)
		except Exception as e:
			print(bcolors.fail("ERROR:"), "Could not delete temp dir", bcolors.okblue(self.tempdir))
			print(e)
			exit(4)

	def getOutputFile(self):
		"""
		Get the calculated result of the absolute file path for the target output file
		@return Absolute file path to target output file
		"""
		return self.output

class bcolors:
    
    @staticmethod
    def okblue(s):
    	return colorama.Fore.BLUE + s + colorama.Style.RESET_ALL

    @staticmethod
    def okgreen(s):
    	return colorama.Fore.GREEN + s + colorama.Style.RESET_ALL


    @staticmethod
    def fail(s):
    	return colorama.Fore.RED + s + colorama.Style.RESET_ALL

if __name__ == "__main__":
	Main()