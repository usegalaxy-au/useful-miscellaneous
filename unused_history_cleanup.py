#!/usr/bin/env python

"""
usnused_history_cleanup.py

A script to help administer storage by:
    * Send users email if their history hasn't been updated for "threshold 1"
      weeks, telling them it will automatically be deleted by
      "threshold 2" (some further weeks).
    * Mark deleted - histories that haven't been updated for "threshold 2"
      weeks, haven't been published or shared, haven't been previously deleted.

It is intended that this script is used in a broader shell script that includes
the pg_cleanup.py script running actual history and associated dataset deletion
and purge.

It needs a config file in yaml format as follows:

---
pg_host: <db_server_dns>
pg_port: <pgsql_port_number>
pg_user: galaxy
pg_dbname: galaxy
pg_password: <password>
warn_weeks: 11
delete_weeks: 13

Author: Simon Gladman 2018 - University of Melbourne.

License: MIT
"""
from __future__ import print_function

import sys
import os.path
from os import access, R_OK
import argparse
import yaml
from collections import defaultdict

import psycopg2

VERSION = 0.1
PROGRAM_NAME = 'unused_history_cleanup.py'
DESCRIPTION = 'Looks for old histories, warns users of their upcoming deletion and marks previously warned histories as deleted.'

def send_mail():
    return

def transform_hists(hists):
    users = defaultdict()
    user_hists = defaultdict(list)
    for h in hists:
        user_hists[h['uid']].append((h['id'],h['name']))
        users[h['uid']] = {'email': h['email'], 'uname': h['uname']}
    return users, user_hists

def get_old_hists(conn, age, verbose):
    SELECT_Q = """
        SELECT
            h.id, h.name, h.user_id, u.username, u.email
        FROM
            history h, galaxy_user u
        WHERE
            h.user_id = u.id AND
            h.deleted = FALSE AND
            h.published = FALSE AND
            h.update_time < (now() - '%s weeks'::interval);
    """
    if verbose:
        print('Retrieving histories. Running following SQL to get old histories', file=sys.stderr)
        print(SELECT_Q % age, file=sys.stderr)
    curs = conn.cursor()
    curs.execute(SELECT_Q, [age])
    temp = curs.fetchall()
    hists = []
    for t in temp:
        hists.append({'id': t[0], 'name': t[1], 'uid': t[2], 'uname': t[3], 'email': t[4]})
    return hists

def main():
    VERBOSE = False

    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument("-c", "--config", help="YAML Config file to use. Required parameter.", required=('--version' not in sys.argv))
    parser.add_argument("-i", "--info_only", help="Just run the queries and report statistics without emailing users nor altering database.", action='store_true')
    parser.add_argument("--actually_delete_things", help="DANGER: Will run the email query, email the users and update the database marking histories as deleted.", action='store_true')
    parser.add_argument("-s", "--show_config", help="Display the config used and exit. Do not run any queries.", action='store_true')
    parser.add_argument("--version", action='store_true', help='Show the version and exit.')
    parser.add_argument("--verbose", action='store_true', help='Show extra output on STDERR.')

    args = parser.parse_args()

    if args.version:
        print("%s, Version: %.1f" % (PROGRAM_NAME, VERSION))
        return

    if args.verbose:
        VERBOSE = True

    #Check the config file
    if VERBOSE:
        print('Reading config file: %s' % args.config, file=sys.stderr)

    if not os.path.isfile(args.config) or not access(args.config, R_OK):
        print('ERROR: Config file "%s" not found or not readable!' % args.config, file=sys.stderr)
        parser.print_help()
        exit(1)

    conf = yaml.load(open(args.config,'r'))

    #Connection stuff
    pg_host = conf['pg_host']
    pg_port = conf['pg_port']
    pg_dbname = conf['pg_dbname']
    pg_user = conf['pg_user']
    pg_pass = conf['pg_password']

    #Threshold stuff
    warn_threshold = conf['warn_weeks']
    delete_threshold = conf['delete_weeks']

    #Show config only then exit
    if args.show_config:
        print('Database host name: %s' % pg_host)
        print('Database port: %s' % pg_port)
        print('Database name: %s' % pg_dbname)
        print('Datbase user: %s' % pg_user)
        print('Warning threshold: %s weeks' % warn_threshold)
        print('Delete threshold: %s weeks' % delete_threshold)
        return

    #Ok, everything past here will require a connection...
    #Create a connection object
    conn = psycopg2.connect(host=pg_host, port=pg_port, user=pg_user, dbname=pg_dbname, password=pg_pass)

    if VERBOSE:
        print("Connection: %s" % conn, file=sys.stderr)

    #Info Only: Print out lists of users and their histories to be:
    #   * Warned
    #   * Deleted
    if args.info_only:
        warn_hists = get_old_hists(conn, warn_threshold, VERBOSE)
        delete_hists = get_old_hists(conn, delete_threshold, VERBOSE)
        print('*******************************')
        if VERBOSE:
            print('The following users will get warnings (Histories are %i weeks old):' % warn_threshold)
        else:
            print('Number of users with %i week old histories to be warned and number histories to be warned about:' % warn_threshold)
        user_warns, user_warn_hists = transform_hists(warn_hists)
        hist_count = 0
        user_count = 0
        for u in user_warns.keys():
            if VERBOSE:
                print('User: %s, %s' % (user_warns[u]['uname'], user_warns[u]['email']))
            for h in user_warn_hists[u]:
                if VERBOSE:
                    print('\tHistory: %s\t%s' % (h[0], h[1]))
                hist_count += 1
            user_count += 1
        print('Users to be warned: %i' % user_count)
        print('Histories to be warned about: %i' % hist_count)
        print('*******************************')
        if VERBOSE:
            print('The following %i weeks old histories would be marked as deleted:' % delete_threshold)
            for h in delete_hists:
                print('History: %s\t%s' % (h['id'],h['name']))
        else:
            print('The number of %i weeks old histories to be marked as deleted: %i' % (delete_threshold, len(delete_hists)))
        return

    if args.actually_delete_things:
        return

if __name__ == "__main__": main()
