#!/usr/bin/env python
# -*- python -*-

import sys
import argparse
import json
import subprocess
import logging
import logging.handlers 
import urllib2
import urllib
from pprint import pformat
import os
import ConfigParser

from utilities.drivers.hbpIncf import *
from utilities.drivers.euhit import *
from utilities.drivers.myproxy import *
from utilities.drivers.eudatunity import *

logger = logging.getLogger('remote.users.sync')

class SyncRemoteUsers:
    
    def __init__(self):
        """initialize the object"""

        self.logger = logger


    def main(self):
        """
        It synchronizes the remote users accounts with a local json file
        """
        
        parser = argparse.ArgumentParser(description='Synchronize remote user '
                                                     'accounts to a local json '
                                                     'file.')
        parser.add_argument('-r', '--remove', action='store_true', dest='remove',
                            default=False, help='remove users and groups that do'
                                               ' not exist in the remote domain')
        parser.add_argument('-d', '--debug', action='store_true', 
                            dest='debug', default=False, 
                            help='print debug messages')
        parser.add_argument('conf', default='remote.users.sync.conf',
                            help='path to the configuration file')

        subparsers = parser.add_subparsers(title='Target group',
                                           help='additional help')
        parser_group = subparsers.add_parser('syncto', 
                                             help='the syncronization target')
        parser_group.add_argument('group', help='the target group (or project)')
        parser_group.add_argument('-s', '--subgroup', dest='subgroup',
                                  default='', help='the target sub-group')

        _args = parser.parse_args()

        self.config = ConfigParser.RawConfigParser()
        self.config.readfp(open(_args.conf))
        logfilepath = self._getConfOption('Common', 'logfile')
        loglevel = self._getConfOption('Common', 'loglevel')
        self.filepath = self._getConfOption('Common', 'usersfile')
        self.dnsfilepath = self._getConfOption('Common', 'dnsfile')
        
        main_project = _args.group
        subproject = _args.subgroup
        remove = _args.remove
        
        ll = {'INFO': logging.INFO, 'DEBUG': logging.DEBUG, \
              'ERROR': logging.ERROR, 'WARNING': logging.WARNING}
        self.logger.setLevel(ll[loglevel])
        if (_args.debug): 
            self.logger.setLevel(logging.DEBUG)

        rfh = logging.handlers.RotatingFileHandler(logfilepath, 
                                                   maxBytes=4194304,
                                                   backupCount=1)
        formatter = logging.Formatter('%(asctime)s %(levelname)s:%(message)s')
        rfh.setFormatter(formatter)
        self.logger.addHandler(rfh)
        
        userparam = {k:v for k,v in self.config.items(main_project)}
        data = None
        # Get the json file containing the list of projects, sub-groups and 
        # related members
        try:
            with open(self.filepath, "r") as jsonFile:
                try:
                    data = json.load(jsonFile)
                    if not main_project in data: 
                        if 'type' not in userparam or userparam['type'] != 'attributes':
                            data[main_project] = {"groups": {}, "members": []}
                except (ValueError) as ve:
                    self.logger.error('the file ' + self.filepath + ' is not a valid json.')
                    sys.exit(1)
        except (IOError, OSError) as e:
            with open(self.filepath, "w+") as jsonFile:
                if 'type' not in userparam or userparam['type'] != 'attributes':
                    data = {main_project: {"groups": {}, "members": []}}
                    jsonFile.write(json.dumps(data,indent=2))
        if subproject and not subproject in data[main_project]['groups']:
            if 'ns_prefix' in userparam and userparam['ns_prefix']:
                data[main_project]['groups'][userparam['ns_prefix']+subproject] = []
            else:
                data[main_project]['groups'][subproject] = []

        userdata = None
        # Get the json file containing the list of distinguished names and users
        try:
            with open(self.dnsfilepath, "r") as jsonFile:
                userdata = json.load(jsonFile)
        except (IOError, OSError) as e:
            with open(self.dnsfilepath, "w+") as jsonFile:
                userdata = {}
                jsonFile.write(json.dumps(userdata,indent=2))

        if (main_project == 'EUDAT'):
            self.logger.info('Syncronizing local json file with eudat user DB...')
            eudatRemoteSource = EudatRemoteSource(main_project, subproject,
                                                  userparam, self.logger)
            data = eudatRemoteSource.synchronize_user_db(data)
            userdata = eudatRemoteSource.synchronize_user_attributes(userdata)
        else:
            self.logger.info('Nothing to sync') 
            sys.exit(0)
        
        if data: 
            with open(self.filepath, "w") as jsonFile:
                jsonFile.write(json.dumps(data,indent=2))
            self.logger.info('{0} correctly written!'.format(self.filepath))
        else:
            self.logger.info('No data to write to {0}'.format(self.filepath))

        if userdata: 
            with open(self.dnsfilepath, "w") as jsonFile:
                jsonFile.write(json.dumps(userdata,indent=2))
            self.logger.info('{0} correctly written!'.format(self.dnsfilepath))
        else:
            self.logger.info('No data to write to {0}'.format(self.dnsfilepath))

        sys.exit(0)
    
    
    def _getConfOption(self, section, option):
        """
        get the options from the configuration file
        """

        if (self.config.has_option(section, option)):
            return self.config.get(section, option)
        else:
            self.logger.error('missing parameter %s:%s' % (section,option))
            sys.exit(1)


if __name__ == '__main__':
    SyncRemoteUsers().main()
