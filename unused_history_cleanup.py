#!/usr/bin/env python

"""
usnused_history_cleanup.py

Author: Simon Gladman 2018 - University of Melbourne.

License: MIT

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
server_name: Galaxy Australia
pg_host: <db_server_dns>
pg_port: <pgsql_port_number>
pg_user: galaxy
pg_dbname: galaxy
pg_password: <password>
warn_weeks: 11
delete_weeks: 13

"""
from __future__ import print_function

import sys
import os.path
from os import access, R_OK
import argparse
import yaml
from collections import defaultdict

import psycopg2
import smtplib
from email.mime.text import MIMEText



VERSION = 0.1
PROGRAM_NAME = 'unused_history_cleanup.py'
DESCRIPTION = 'Looks for old histories, warns users of their upcoming deletion and marks previously warned histories as deleted.'

def transform_hists(hists):
    """
    transform_hists

    Takes a list of dictionaries returned from `get_old_hists` and returns a dictionary of unique users
    which contains  their username and email by id and a dictionary of lists of histories for each user id.

    """
    users = defaultdict()
    user_hists = defaultdict(list)
    for h in hists:
        user_hists[h['uid']].append((h['id'],h['name']))
        users[h['uid']] = {'email': h['email'], 'uname': h['uname']}
    return users, user_hists

def get_old_hists(conn, age, verbose):
    """
    get_old_hists

    Takes a psql connection, an age in weeks (int) and the verbosity level, runs a query on the connection
    and returns a list of dictionaries of histories and their user details which haven't been updated for at least
    that many weeks.

    """
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
    curs.close()
    return hists

def subtract_lists(hists1, hists2):
    """
    substracts the records in the second list from the records in the first list
    """
    for h in hists2:
        if h in hists1:
            hists1.remove(h)
    return hists1

def send_email_to_user(user, hists, warn, delete, server, smtp_server, from_addr, response_addr, VERBOSE):
    """
    Sends warning emails to users stating their histories are about to be deleted.
    """

    MSG_TEXT = """
Dear %s,

You are receiving this email as one or more of your histories on the %s server
have not been updated for %i weeks. They will be beyond the User Data Storage time limits soon.
If you do not use or update them within the next %i weeks, they will automatically be deleted
and purged from disk.

You should download any files you wish to keep from this history within the next
%i weeks. Instructions for doing so can be found at:

https://galaxy-au-training.github.io/tutorials/modules/galaxy-data/

The history(ies) in question are as follows:
    """ % (user['uname'], server, warn, delete - warn, delete - warn)
    MSG_TEXT += '\tHistory ID\tName\n'
    for h in hists:
        MSG_TEXT += '\t%s\t\t%s\n' % (h[0],h[1])
    MSG_TEXT += """

You can contact %s if you have any queries.

Yours,

%s Admins.
""" % (response_addr, server)

    email = user['email']
    subject = "%s History Deletion Warning" % server

    if VERBOSE:
        print('Email sent:')
        print("To: %s" % email)
        print("From: %s" % from_addr)
        print("Subject: %s" % subject)
        print("----------------------")
        print(MSG_TEXT)

    mail_server = smtplib.SMTP('localhost')
    msg = MIMEText(MSG_TEXT)
    msg['To'] = email
    msg['From'] = from_addr
    msg['Subject'] = subject
    msg['BCC'] = 'slugger70@gmail.com,g.price@qfab.org'

    mail_server.sendmail(from_addr, [email,'slugger70@gmail.com','g.price@qfab.org'], msg.as_string())

    mail_server.quit()

    return


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

    #Miscellaneous stuff
    server_name = conf['server_name']
    smtp_server = conf['smtp_server']
    from_addr = conf['from_addr']
    response_addr = conf['response_addr']

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

    """
    Info Only: Depending on the verbosity, prints out numbers of or lists of
    users and their histories to be:
       * Warned
       * Deleted
    """
    if args.info_only:
        warn_hists = get_old_hists(conn, warn_threshold, VERBOSE)
        dont_warn_again = get_old_hists(conn, warn_threshold + 1, VERBOSE)
        actually_warn_hists = subtract_lists(warn_hists, dont_warn_again)
        delete_hists = get_old_hists(conn, delete_threshold, VERBOSE)
        print('*******************************')
        if VERBOSE:
            print('The following users will get warnings (Histories are %i weeks old):' % warn_threshold)
        else:
            print('Number of users with %i week old histories to be warned and number histories to be warned about:' % warn_threshold)
        user_warns, user_warn_hists = transform_hists(actually_warn_hists)
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
        """
        This will actually alter the database and actually delete things! Be very careful!
        """
        # First we need to get the deleteable histories.
        delete_hists = get_old_hists(conn, delete_threshold, VERBOSE)
        #Send this dictionary to the delete histories sub.
        if len(delete_hists) > 0:
            hist_ids = []
            for h in delete_hists:
                hist_ids.append(h['id'])
            if VERBOSE:
                print('These histories are to be marked as deleted.')
                for h in hist_ids:
                    print("History: %s" % h)
            UPDATE_Q = """
            UPDATE
                history
            SET
                deleted = TRUE
            WHERE
                id = ANY( %s );
            """
            curr = conn.cursor()
            if VERBOSE:
                print('Running the following query to update the database')
                print(curr.mogrify(UPDATE_Q, (hist_ids,)))
            try:
                curr.execute(UPDATE_Q, (hist_ids,))
                conn.commit()
            except psycopg2.Error as e:
                print('Something went wrong with the commit. Rolling back')
                print(e)
                conn.rollback()
                pass

        # Now we need to email users who are getting warnings. :)
        warn_hists = get_old_hists(conn, warn_threshold, VERBOSE)
        dont_warn_again = get_old_hists(conn, warn_threshold + 1, VERBOSE)
        actually_warn_hists = subtract_lists(warn_hists, dont_warn_again)
        user_warns, user_warn_hists = transform_hists(actually_warn_hists)

        conn.close()

        for u in user_warns.keys():
            send_email_to_user(user_warns[u], user_warn_hists[u], warn_threshold, delete_threshold, server_name, smtp_server, from_addr, response_addr, VERBOSE)
    return


if __name__ == "__main__": main()
