#!/usr/bin/python

class TimeUnit(object):
    sec = 1
    min = 2
    hour = 3
    day = 4
    
    @classmethod
    def tostring(cls, val):
        for k,v in vars(cls).iteritems():
            if v==val:
                return k
    
    @classmethod
    def fromstring(cls, str):
        return getattr(cls, str, TimeUnit.min)

class SnapshotConfiguration:
    repositoryName = "";
    repositoryPath = "";
    snapshotName = "";
    snapshotFrequency = 0;
    snapshotUnits = TimeUnit.sec;
    snapshotLink = "";
    
    def __init__(self, repositoryName, repositoryPath, snapshotName, snapshotFrequency, snapshotLink, snapshotUnit = TimeUnit.min):
        self.repositoryName = repositoryName
        self.repositoryPath = repositoryPath
        self.snapshotName = snapshotName
        self.snapshotFrequency = snapshotFrequency
        self.snapshotLink = snapshotLink
        self.snapshotUnits = snapshotUnit
        
    
    def getFullName(self):
        return self.repositoryName + ":" + self.snapshotName
    
    def __str__(self):
        return "Snapshot (%s): \n \t Repository Name: %s \n" \
                            "\t Repository Path: %s \n" \
                            "\t Snapshot Name: %s \n" \
                            "\t Snapshot Frequency: %s \n" \
                            "\t Snapshot Time Unit: %s \n" \
                            "\t Snapshot Link: %s \n" % (self.getFullName(),
                                                         self.repositoryName, 
                                                         self.repositoryPath, 
                                                         self.snapshotName,
                                                         self.snapshotFrequency,
                                                         TimeUnit.tostring(self.snapshotUnits),
                                                         self.snapshotLink)