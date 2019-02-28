#!/usr/bin/env python

from __future__ import print_function

import sys
import os
from os import access, R_OK
import argparse
import yaml

VERSION = 0.1
PROGRAM_NAME = 'pull_galaxy_config.py'
DESCRIPTION = 'Will download all requisite config files from a galaxy server'

DIR_EXISTS = 3

def make_dir(dirname, VERBOSE):
    try:
        os.makedirs(dirname, exist_ok=True)
    except OSError as e:
        print ("ERROR: Creation of the directory %s failed" % dirname, file=sys.stderr)
        print(e)
        exit(1)
    else:
        if VERBOSE:
            print ("Successfully created the directory %s " % dirname, file=sys.stderr)

def main():
    VERBOSE = False

    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument("-c", "--config", help="YAML Config file to use. Required parameter.", required=('--version' not in sys.argv))
    parser.add_argument("-o", "--outdir", help="Name of output directory in which to write the downloaded config files.")
    #parser.add_argument('-s', '--server', help='The address of the server (e.g. usegalaxy.org.au)')
    #parser.add_argument('-k', '--key_file', help='The ssh key file to use for remote connection to the server.')
    #parser.add_argument('-u', '--username', help='The ssh username to use')
    #parser.add_argument('-p', '--path', help='The path on the remote machine to the Galaxy root')
    #parser.add_argument('-f', '--files', help='An array containing the files to download. e.g. \'["config/galaxy.yml", "config/tool_conf.xml", "..var/integrated_tool_panel.xml"]\'')
    parser.add_argument("--force", action='store_true', help='Force overwrite of contents of existing output directory.')
    parser.add_argument("--version", action='store_true', help='Show the version and exit.')
    parser.add_argument("--verbose", action='store_true', help='Show extra output on STDERR.')

    args = parser.parse_args()

    if args.version:
        print("%s, Version: %.1f" % (PROGRAM_NAME, VERSION))
        return

    if args.verbose:
        VERBOSE = True

    outdir = args.outdir

    #Check the config file
    if VERBOSE:
        print('Reading config file: %s' % args.config, file=sys.stderr)

    if not os.path.isfile(args.config) or not access(args.config, R_OK):
        print('ERROR: Config file "%s" not found or not readable!' % args.config, file=sys.stderr)
        parser.print_help()
        exit(1)

    conf = yaml.load(open(args.config,'r'))

    key = conf['key_file']
    user = conf['username']
    server = conf['server_address']
    path = conf['galaxy_path']
    files = conf['files']

    if VERBOSE:
        print(key)
        print(user)
        print(server)
        print(path)
        print(files)

    dirlist = []

    galaxyname = path.split('/')[-1]
    dirlist.append(outdir + '/' + galaxyname)

    for f in files:
        dir = outdir + '/' + galaxyname + '/' + '/'.join(f.split('/')[:-1])
        if not dir in dirlist:
            dirlist.append(dir)

    for d in dirlist:
        if os.path.exists(d):
            if args.force:
                if VERBOSE:
                    print("WARNING: %s directory already exists. Using --force to overwrite contents" % outdir, file=sys.stderr)
            else:
                print("ERROR: %s already exists. Either choose a different directory or use --force (force will overwrite contents of the directory). Exiting" % outdir, file=sys.stderr)
                exit(3)
        else:
            make_dir(d, VERBOSE)

    for f in files:
        if VERBOSE:
            print("Downloading: %s" % f, file=sys.stderr)
        remotename = path + '/' + f
        localname = outdir + '/' + galaxyname + '/' + f
        command = 'scp -i "%s" "%s@%s:%s" "%s"' % (key, user, server, remotename, localname)
        if VERBOSE:
            print('Command: %s' % command, file=sys.stderr)
        try:
            os.system(command)
        except OSError as e:
            print ("ERROR: Downloading of the file: %s failed" % f, file=sys.stderr)
            print(e)
            pass
        else:
            if VERBOSE:
                print ("Successfully downloaded the file %s " % f, file=sys.stderr)


if __name__ == "__main__": main()
