Script to search and replace specific strings in all songs in an EasyWorship (EW) Schedule file. Supports regex lookup.
Tested with EasyWorship 6 on Unix and Windows systems. Should work with EasyWorship 6 (EW6) and newer. Requires Python3 or later.

An EW6 schedule is a zipped sqlite database. This script is nothing more than a way to extract that database from the ZIP container and automatically perform the required SQL queries to search and update the required strings in that database. To update the EW6 database itself, add all items to a schedule, run this script on that schedule, and import the new schedule back into EW6.

usage: `scheduleConverter.py [-h] [-r] [-i] [-d] input output search replace`

Replace specific items in an EasyWorship Schedule File (.EWSX)

positional arguments:
  `input`              The filename of the schedule to update
  `output`             The desired name of the output schedule
  `search`             The string to replace in the schedule
  `replace`            The string to replace the search string with in the schedule

optional arguments:
  `-h`, `--help`        show this help message and exit
  `-r`, `--regex`        Treat search and replace strings as regular expressions, including usage of groups
  `-i`, `--ignore-case`  Ignore case in search string
  `-d`, `--dry-run`      Print updated values instead of writing directly to database. Useful for finding the right search and replace strings

