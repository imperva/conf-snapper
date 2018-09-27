#!/usr/bin/python

import logging
import subprocess
from datetime import datetime
import os

import SnapshotConfiguration

class BtrfsStorage:
    
    genSnapshotPathSubFolder = '/snapshots/'
    snapshotPrefix = 'snapshot-'
        
    def checkRepository(self, path):
        logger = logging.getLogger();
        
        logger.debug("started") 
        
        check_btrfs_command = 'stat -f --format=%T ' + path;
        
        logger.debug("Running '%s'", check_btrfs_command) 
        
        output = subprocess.Popen(check_btrfs_command.split(), stdout=subprocess.PIPE).communicate()[0]
        logger.debug("The path %s is %s", path, output) 
        
        if output.strip() == 'btrfs':
            return True;
        
        return False;
        
    def getSnapshotFolder(self, snapshot):
        logger = logging.getLogger();
        
        snapshotRootFolder = snapshot.repositoryPath + self.genSnapshotPathSubFolder 
        snapshotFolder = snapshotRootFolder + snapshot.snapshotName
        
        if os.path.exists(snapshotRootFolder) == False:
            logger.debug("Folder '%s' does not exist, creating...", snapshotRootFolder)
            create_folder_command = 'sudo mkdir ' + snapshotRootFolder
            os.system(create_folder_command)
        
        if os.path.exists(snapshotFolder) == False:
            logger.debug("Folder '%s' does not exist, creating...", snapshotFolder)
            create_folder_command = 'sudo mkdir ' + snapshotFolder
            os.system(create_folder_command)
        
        return snapshotFolder;
    
    def takeSnapshot(self, snapshot):
        logger = logging.getLogger();
        
        logger.debug("started") 
        
        time_now = datetime.now()
        snapshotName = self.snapshotPrefix + time_now.strftime("%Y-%m-%d_%H-%M-%S")
        
        snapshot_folder = self.getSnapshotFolder(snapshot)
        snapshot_path = snapshot_folder + '/' + snapshotName
        create_snapshot_command = 'sudo btrfs subvolume snapshot ' + snapshot.repositoryPath + ' ' + snapshot_path;
        
        logger.debug("command is '%s' ", create_snapshot_command) 
        
        output = subprocess.Popen(create_snapshot_command.split(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT).communicate()[0]
        logger.debug("The output is '%s'",output) 
        
        if('ERROR' in output or 'usage' in output):
            logger.error('Failed to create (%s) snapshot.')
            return False
        
        return True;
        
    def getSnapshotCreatingTime(self, snapshotName):
        logger = logging.getLogger();
        snapshotTime = snapshotName[len(self.snapshotPrefix):]

        #logger.debug("SnapshotName: %s, snashotTime: %s", snapshotName, snapshotTime);
        date_object = datetime.strptime(snapshotTime, '%Y-%m-%d_%H-%M-%S')
        
        return date_object;    
    
    def deleteSnapshot(self, snapshot, forceDelete = False):
        logger = logging.getLogger();
        
        logger.debug("started") 
        
        snapshot_folder = self.getSnapshotFolder(snapshot)
        
        def sorted_ls(path):
            mtime = lambda f: self.getSnapshotCreatingTime(os.path.basename(f))
            return list(sorted(os.listdir(path), key=mtime))
        
        sorted_folders = sorted_ls(snapshot_folder)
        sorted_folders_len = len(sorted_folders)
        
        if forceDelete == False and sorted_folders_len < 3:
            logger.debug("There is less than 3 snapshots, nothing to delete.")
            return sorted_folders;
        
        logger.debug(sorted_ls(snapshot_folder))
        
        actual_number_of_will_be_delete_snapshot = sorted_folders_len;
        if forceDelete == False :
            actual_number_of_will_be_delete_snapshot = sorted_folders_len-2
        
        logger.debug("There %d snapshots, %d will be deleted.", sorted_folders_len, actual_number_of_will_be_delete_snapshot)
    
        current_snapshot_list = []
        for idx, snapshotName in enumerate(sorted_folders):
            full_snapshot_path = snapshot_folder + '/' + snapshotName;
            
            if((idx + 1) > (actual_number_of_will_be_delete_snapshot)):
                logger.debug("Snapshot %s has left.", snapshotName)
                current_snapshot_list.append(snapshotName)
                continue;
#           
            create_snapshot_command = 'sudo btrfs subvolume del ' + full_snapshot_path;
        
            logger.debug("command is '%s' ", create_snapshot_command) 
            
            output = subprocess.Popen(create_snapshot_command.split(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT).communicate()[0]
            logger.debug("The output is '%s'",output) 
            
            if('ERROR' in output or 'usage' in output):
                logger.error('Failed to delete (%s) snapshot.', full_snapshot_path)
            
        
        return current_snapshot_list;
        
        