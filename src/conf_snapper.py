#!/usr/bin/python

""" 
    This is a script that runs configuration snapper for Btrfs. Configuration is provided
    in a file. 
"""

import argparse
import datetime
import json
import logging
import os
import signal
import socket
import sys
import threading
import time
import traceback
# requires installation of schedule
# sudo apt-get -y install python-pip
# sudo pip install apscheduler
from apscheduler.schedulers.blocking import BlockingScheduler
from logging.handlers import RotatingFileHandler

import BtrfsStorage
import SnapshotConfiguration
from SnapshotConfiguration import TimeUnit

log_file_name = 'conf_snapper.log';
log_file = '/var/log/conf_snapper/' + log_file_name;

global_stopper_list = [];

#TODO: change DEBUG to INFO (before full production deployment) 
log_level = logging.DEBUG

#Singleton Btrfs storage defined as a snapshot Facade 
btrfs = BtrfsStorage.BtrfsStorage()

snapper_status_file = "/var/log/conf_snapper/snapper_status.json"

class StateStatus(object):
    up = "up"
    down = "down"
    suspended = "suspended"
    stopped = "stopped"

class State: 
    status = StateStatus.down;
    hasConfigurationError = False;
    configurationErrorReason = ""
    hasRuntimeError = False;
    runtimeErrorReason = ""

    def writeStatusJson(self):
        logger = logging.getLogger();
        json_data_string = {}
        json_data_string["status"] = self.status        
        json_data_string["hasConfigurationError"] = self.hasConfigurationError
        json_data_string["hasRuntimeError"] = self.hasRuntimeError
        json_data_string["configurationErrorReason"] = self.configurationErrorReason
        json_data_string["runtimeErrorReason"] = self.runtimeErrorReason
        with open(snapper_status_file, 'w') as outfile:
            json.dump(json_data_string, outfile)
        logger.info("Writing current status...")    

    def reset(self):
        self.status = StateStatus.down;
        self.hasConfigurationError = False;
        self.configurationErrorReason = ""
        self.hasRuntimeError = False;
        self.runtimeErrorReason = ""

    
state = State()
 
#------------- Global functions section. Mainly used by scheduler ------------------

# Function returns one snapshot before last. Expects time sorted list in snapshots.
def getPreviousPathToSnapshot(snapshots, snappshot):
    logger = logging.getLogger();
    
    snapshot_len = len(snapshots)
    logger.debug(snapshots)
    
    if(snapshot_len == 0) :
        logger.error("Wrong number of snapshots (%d), 2 is expected, returns None", snapshot_len);
        state.hasRuntimeError = True;
        state.hasRuntimeError = "Wrong number of snapshots " + snapshot_len + " 2 is expected. Snapshot: " + snappshot.snapshotName;
        state.writeStatusJson();
        return None
    
    if(snapshot_len > 2) :
        logger.error("Wrong number of snapshots (%d), 2 is expected, takes the last %s", snapshot_len, snapshots[-1]);
        state.hasRuntimeError = True;
        state.hasRuntimeError = "Wrong number of snapshots " + snapshot_len + " 2 is expected, takes the last " + snapshots[-1] + ".Snapshot: " + snappshot.snapshotName;
        state.writeStatusJson();        
        return snapshots[-1]
    
    return snapshots[0]

# Function returns last snapshot. Expects time sorted list in snapshots.
def getLastPathToSnapshot(snapshots, snappshot):
    logger = logging.getLogger();
    
    snapshot_len = len(snapshots)
    logger.debug(snapshots)
    
    if(snapshot_len == 0) :
        logger.error("Wrong number of snapshots (%d), 2 is expected, returns None", snapshot_len);
        return None
    
    return snapshots[-1]
    
#Function creates or updates (remove->create) symbolic link for given snapshot.         
def createSymbolicLink(snapshot, snapshotPath):
    logger = logging.getLogger();
    
    if(snapshotPath == None):
        logger.error("Path is None, do nothing.")
        return
    
    snapshotRootPath = btrfs.getSnapshotFolder(snapshot)
    fullName = snapshotRootPath + '/' + snapshotPath

    symbolicLinkPath = snapshot.snapshotLink;
    
    logger.info("Creating symbolic link '%s' to path '%s", symbolicLinkPath, fullName)
    
    if os.geteuid() != 0:
        logger.error("The script was run without root privileges. Symbolic link will not be created.")
    else:
        if os.path.islink(symbolicLinkPath):
            logger.debug("The path %s exist, removing it.", symbolicLinkPath)
            os.unlink(symbolicLinkPath)
        else:
            logger.debug("The path %s does not exist.", symbolicLinkPath)
        os.symlink(fullName, symbolicLinkPath)
    

def isServiceDisabled():
    logger = logging.getLogger();
    logger.debug("Checking if snapshot should be taken.")
    
    for stopper in global_stopper_list:
        if os.path.exists(stopper) == True:
            logger.debug("File %s exists!", stopper)
            state.status = StateStatus.suspended;
            state.writeStatusJson();
            return False;
        
    state.status = StateStatus.up
    state.writeStatusJson();
    return True;
    

# Creates snapshot according to snapshot configuration. 
# Mainly, this function is used by scheduler, but also can be used directly from code.
# The difference between sched and manual call is future link updates which are not created in manual creation. 
def takeSnapshot(snapper, snapshot, isManualCall = False):
#         self.logger.info("I'm working....")
    snapper.logger.info("Snapshot %s will be taken", snapshot.getFullName())
    if isServiceDisabled() == False:
        snapper.logger.info("Service is disabled, ignoring...");
        return;
    
    if btrfs.takeSnapshot(snapshot) == False:
        state.hasRuntimeError = True;
        state.runtimeErrorReason = "Failed to create snapshot for " + snapshot.getFullName() + " repository";
    
    current_snapshots = btrfs.deleteSnapshot(snapshot)
    #assuming all file names are sorted according to creation time.
    
    createSymbolicLink(snapshot, getPreviousPathToSnapshot(current_snapshots, snapshot));
    
    if isManualCall == False:
        #add new job for replacing symbolic link to latest one
        time_now = int(time.time())
        
        if snapshot.snapshotUnits == TimeUnit.sec:
            time_now += (snapshot.snapshotFrequency/2)
        elif snapshot.snapshotUnits == TimeUnit.min:
            time_now += ((snapshot.snapshotFrequency*60)/2)
        elif snapshot.snapshotUnits == TimeUnit.hour:
            time_now += ((snapshot.snapshotFrequency*60*60)/2)
        elif snapshot.snapshotUnits == TimeUnit.day:
            time_now += ((snapshot.snapshotFrequency*60*60*24)/2)
        else:
            snapper.logger.error("Wrong time unit.")
        
        nextTimeStr = datetime.datetime.fromtimestamp(time_now).strftime("%Y-%m-%d %H:%M:%S")
        snapper.logger.debug('nextTimeStr: ' + nextTimeStr)
        
        snapper.sched.add_job(updateSnapshotLink, 'date', run_date=nextTimeStr, args=[current_snapshots, snapshot])
    

# Updates snapshot link scheduled by scheduler. 
def updateSnapshotLink(current_snapshots, snapshot):
    logger = logging.getLogger();
    logger.debug("Going to update symbolic link to latest snapshot.\n")
    
    if isServiceDisabled() == False:
        snapper.logger.info("Service is disabled, ignoring...");
        return;

    createSymbolicLink(snapshot, getLastPathToSnapshot(current_snapshots, snapshot));
    
# Cleans all jobs and terminates a scheduler. 
def shutdown(snapper):
    snapper.sched.remove_all_jobs();
    snapper.sched.shutdown();

# Global helper for all snapshots cleaning.
# Can be used for manual cleaning as well as Btrfs uninstal. 
def detele_all_snapshots_for_all_repositories(snapper):
    logger = logging.getLogger();
    logger.info("Going to delete all snapshots for all repositories.")
    print "Going to delete all snapshots for all repositories.\n";
    for snapshot in snapper.configuration:
        logger.info("Deleting all snapshots for snapshot %s.\n", snapshot.getFullName())
        print "Deleting all snapshots for snapshot " +  snapshot.getFullName();
        btrfs.deleteSnapshot(snapshot, True);
        
        symbolicLinkPath = snapshot.snapshotLink;
        
        if os.path.islink(symbolicLinkPath):
            print "Deleting link " + symbolicLinkPath 
            logger.info("Deleting link " + symbolicLinkPath)
            os.unlink(symbolicLinkPath)
            
    print "Deletion has been finished. For more information please check " + log_file 
    logger.info("Deletion has been finished. Please check '" + log_file + "' for more information")
    
#helper function for single process execution.
def get_lock(process_name):
    logger = logging.getLogger();
    global lock_socket   # Without this our lock gets garbage collected
    lock_socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    
    try:
        lock_socket.bind('\0' + process_name)
        logger.info("I got the lock. I'm a single process.")
    
    except socket.error:
        logger.error("There is an another instance of %s is  running.", process_name)
        print "There is an another instance of '" +  process_name + "' is  running.", process_name
        sys.exit(10)


# --------------------- Snapper section -----------------------------
class Snapper:
    configuration = [];
    sched = None;

    def __init__(self):

        # log initialization 
        self.logger = logging.getLogger()
        hdlr = RotatingFileHandler(log_file, maxBytes=1024*1024*20, backupCount=4)
        
        # hdlr2 - used for stdout (system.out).
        hdlr2 = logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)s (%(thread)d) %(levelname)s\t%(funcName)s:  %(message)s", "%Y-%m-%d %H:%M:%S")
        hdlr.setFormatter(formatter)
        hdlr2.setFormatter(formatter)
        self.logger.addHandler(hdlr)
        
        #Enable hdlr2 for manual running and logs to system.out. 
        #self.logger.addHandler(hdlr2)
        
        self.logger.setLevel(log_level)
        
        # default configuration file.
        self.conf_file = '/etc/conf_snapper/snapper_conf.json'
        self.running = True
        
    #Validation for first time run
    def checkSnapsotOnStartUp(self, snapshot):
        symbolicLinkPath = snapshot.snapshotLink;
        
        if os.path.islink(symbolicLinkPath):
            logger.debug("The path %s exist. Noting to do.", symbolicLinkPath)
            return;
        
        logger.debug("The path %s does not exist on startup, creating first snapshot.", symbolicLinkPath)
        takeSnapshot(self, snapshot, True)
    
    # Configuration loader
    def config(self, alt_path):
        if alt_path != None:
            self.conf_file = alt_path
        self.logger.info("Using configuration file %s", self.conf_file)
        
        with open(self.conf_file) as fh:
            self.logger.debug("Loaded conf file.")
            
            json_snapper_configuration = json.load(fh)['snapper_configuration']
            
            repositories = json_snapper_configuration['repositories']
            for repository in repositories:
                
                if not repository.get('name'):
                    self.logger.debug("Name parameter was not fount... continue")
                    state.hasConfigurationError = True;
                    state.configurationErrorReason = "Name parameter was not fount...";
                    continue
                
                for snapshot in repository['snapshot_levels']:
                    snapshotConf = SnapshotConfiguration.SnapshotConfiguration(repository['name'],
                                                                               repository['path'],
                                                                               snapshot['name'],
                                                                               snapshot['frequency'],
                                                                               snapshot['link'],
                                                                               TimeUnit.fromstring(snapshot['unit'])
                                                                               );
                    self.logger.debug("%s loaded", snapshotConf.getFullName());    
                    self.logger.debug(snapshotConf); 
                    
                    if btrfs.checkRepository(snapshotConf.repositoryPath) == False:
                        self.logger.error("Repository path (%s) is not valid Btrfs folder", snapshotConf.repositoryPath)
                        state.hasConfigurationError = True;
                        state.configurationErrorReason = "Repository path " + snapshotConf.repositoryPath + " is not valid Btrfs folder";
                        continue
                    else:
                        self.logger.debug("Repository path (%s) is valid Btrfs folder", snapshotConf.repositoryPath)
                    
                    if snapshotConf.snapshotLink == "":
                        self.logger.error("Repository link (%s) is empty", snapshotConf.snapshotLink)
                        state.hasConfigurationError = True;
                        state.configurationErrorReason = "Repository link is empty.";
                    else:
                        self.configuration.append(snapshotConf);
            
            try:
                stoppers = json_snapper_configuration['stoppers']
                for stopper in stoppers:
                    global_stopper_list.append(stopper)
            except Exception, err:
                state.hasConfigurationError = True;
                state.configurationErrorReason = "Stopper section does not exist. - " + traceback.format_exc();
                logger.error("\n Stopper section does not exist. - %s\n" % traceback.format_exc())
            
 
    def startSecJob(self, cbFunction, expression, snapshotConfig):
        self.sched.add_job(cbFunction, 'cron', second=expression, args=[self, snapshotConfig], name=snapshotConfig.getFullName())
        
    def startMinJob(self, cbFunction, expression, snapshotConfig):
        self.sched.add_job(cbFunction, 'cron', minute=expression, args=[self, snapshotConfig], name=snapshotConfig.getFullName() )
    
    def startHourJob(self, cbFunction, expression, snapshotConfig):
        self.sched.add_job(cbFunction, 'cron', hour=expression, args=[self, snapshotConfig], name=snapshotConfig.getFullName() )

    def startDayJob(self, cbFunction, expression, snapshotConfig):
        self.sched.add_job(cbFunction, 'cron', day=expression, args=[self, snapshotConfig], name=snapshotConfig.getFullName() )
        
    def start(self):
        try:
            # apscheduler::BlockingScheduler initialization. 
            self.sched = BlockingScheduler();
            
            for snapshotConf in self.configuration:
                
                #Take snapshots on startup
                self.checkSnapsotOnStartUp(snapshotConf);
                
                switcher = {
                    TimeUnit.sec: self.startSecJob,
                    TimeUnit.min: self.startMinJob,
                    TimeUnit.hour: self.startHourJob,
                    TimeUnit.day: self.startDayJob,
                }
                
                expression = '*/' + str(snapshotConf.snapshotFrequency)
                func = switcher.get(snapshotConf.snapshotUnits)
                
                #add takeSnapshot job.
                func(takeSnapshot, expression, snapshotConf)
                
            self.sched.start()
        
        except Exception, err:
            state.status = StateStatus.down;
            state.hasRuntimeError = True;
            state.configurationErrorReason = "Failed to start with exception: " + traceback.format_exc();
            state.writeStatusJson();
            sys.exit("\nFailed to start - %s\n" % traceback.format_exc())


    def set_signal_handling(self, sig, frame):
        logger = logging.getLogger(); 
        
        #SIGINT for Ctrl+C.
        #SIGTERM for stop/start service.
        if sig == signal.SIGTERM or sig == signal.SIGINT:
            print "Got a termination signal. Exiting..."
            self.running = False
            self.logger.info("Got a termination signal")
            if self != None and self.sched !=None:
                logger.debug("Stopping the scheduler...")
                shutdown(self);
            else:
                logger.debug("self or sched is NONE")
                
            state.status = StateStatus.stopped;
            state.runtimeErrorReason = "Got a termination signal.";
            state.writeStatusJson();
            
    def printConfiguration(self):
        print "Snapper configuration:"
        for conf in self.configuration:
            print conf

# -------------------- Main Section ------------------------
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Snapshot manager for Btrfs')
    parser.add_argument('-c','--check', 
                        help='Check configuration file.',
                        action='store_true',
                        dest='is_check')
    parser.add_argument('-d','--delete-all', 
                        help='Deletes all snapshots.',
                        action='store_true',
                        dest='is_delete')
    parser.add_argument('configuration_file', 
                        metavar='<configuration_file_path>', 
                        type=argparse.FileType('r'),
                        nargs='?',
                        help='configuration file path')
    
    args = parser.parse_args()
    condiguration_file = args.configuration_file
    is_check_configuration = args.is_check
    is_snapshots_delete = args.is_delete
    
    try:
        
        # user root validation.
        if os.geteuid() != 0:
            log_file = log_file_name;
            sys.exit("\nOnly root user can run this script\n")
            
        snapper = Snapper();
        logger = logging.getLogger();
        
        get_lock('conf_snapper')
        
        try:
            if condiguration_file != None:
                snapper.config(condiguration_file.name)
            else:
                snapper.config(None)
                # snapper.config('snapper_conf.json')
            
            if args.is_check:
                snapper.printConfiguration();
                sys.exit(0);
            
        except Exception, err:
            logger.error("\nFailed to parse configuration - %s\n" % traceback.format_exc())
            
            state.status = StateStatus.down;
            state.hasConfigurationError = True;
            state.configurationErrorReason = "Failed to parse configuration - " + traceback.format_exc();
            state.writeStatusJson();
            
            sys.exit("\nFailed to parse configuration - %s\n" % traceback.format_exc())
            
        if is_snapshots_delete == True:
            detele_all_snapshots_for_all_repositories(snapper);
            sys.exit(0);
        
        signal.signal(signal.SIGTERM, snapper.set_signal_handling)
        signal.signal(signal.SIGINT, snapper.set_signal_handling)
        
        process_thread = threading.Thread(target=snapper.start, name="process_thread")
        process_thread.start()
        
        state.status = StateStatus.up;
        state.writeStatusJson();
        
        while process_thread.is_alive():
            time.sleep(1)
        process_thread.join()
    
    except Exception, err:
        state.status = StateStatus.down;
        state.hasRuntimeError = True;
        state.configurationErrorReason = "Failed to start with exception: " + traceback.format_exc();
        state.writeStatusJson();
        
        sys.exit("\nFailed to start - %s\n" % traceback.format_exc())
        
