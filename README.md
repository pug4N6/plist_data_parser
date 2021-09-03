# plist_data_parser
Parses plist data to an SQLite database file

Plist files come in a variety of formats (XML, binary, NSKeyedArchiver). They are found in a variety of formats (as files, as database blobs, embedded in other files or data blobs). 

This Python script will attempt to parse plist data from a file or folder and export the information to an SQLite database, which can then be searched or filtered to help find relevant keys/values.

Currently, Boolean plist values are convered to "True/False" in the output, and binary data is exported in its raw format.

The roadmap for the script is to provide support for recursively parsing the results additional plist data and to allow parsing of plist data from a target SQLite database file.
