# -*- coding: utf-8 -*-

'''
Faraday Penetration Test IDE
Copyright (C) 2013  Infobyte LLC (http://www.infobytesec.com/)
See the file 'doc/LICENSE' for the license information

'''
import restkit
import re

from model.workspace import Workspace
from persistence.persistence_managers import DBTYPE

from model.guiapi import notification_center

from config.configuration import getInstanceConfiguration
from config.globals import CONST_BLACKDBS
CONF = getInstanceConfiguration()


class WorkspaceException(Exception):
    pass


class WorkspaceManager(object):
    """
    Workspace Manager class
    Its responsibilities goes from:
        * Workspace creation
        * Workspace removal
        * Workspace opening
        * Active Workspace switching
    """

    def __init__(self, dbManager, mappersManager,
                 changesManager, *args, **kwargs):
        self.dbManager = dbManager
        self.mappersManager = mappersManager
        self.changesManager = changesManager
        self.active_workspace = None

    def getWorkspacesNames(self):
        """Returns the names of the workspaces as a list of strings"""
        return self.dbManager.getAllDbNames()

    def createWorkspace(self, name, desc, dbtype=DBTYPE.COUCHDB):
        workspace = Workspace(name, desc)
        try:
            dbConnector = self.dbManager.createDb(name, dbtype)
        except restkit.Unauthorized:
            raise WorkspaceException(
                ("You're not authorized to create workspaces\n"
                 "Make sure you're an admin and add your credentials"
                 "to your user configuration "
                 "file in $HOME/.faraday/config/user.xml\n"
                 "For example: "
                 "<couch_uri>http://john:password@127.0.0.1:5984</couch_uri>"))
        except Exception as e:
            raise WorkspaceException(str(e))
        if dbConnector:
            self.closeWorkspace()
            self.mappersManager.createMappers(dbConnector)
            self.mappersManager.save(workspace)
            self.setActiveWorkspace(workspace)
            notification_center.workspaceChanged(
                workspace, self.getWorkspaceType(name))
            notification_center.workspaceLoad(workspace.getHosts())
            self.changesManager.watch(self.mappersManager, dbConnector)
            return workspace
        return False

    def openWorkspace(self, name):
        """Open a workspace by name. Returns the workspace. Raises an
        WorkspaceException if something went wrong along the way.
        """
        if name not in self.getWorkspacesNames():
            raise WorkspaceException(
                "Workspace %s wasn't found" % name)
        self.closeWorkspace()
        try:
            dbConnector = self.dbManager.getConnector(name)
        except restkit.Unauthorized:
            raise WorkspaceException(
                ("You're not authorized to access this workspace\n"
                 "Add your credentials to your user configuration "
                 "file in $HOME/.faraday/config/user.xml\n"
                 "For example: "
                 "<couch_uri>http://john:password@127.0.0.1:5984</couch_uri>"))
        except Exception as e:
            notification_center.CouchDBConnectionProblem(e)
            raise WorkspaceException(str(e))
        self.mappersManager.createMappers(dbConnector)
        workspace = self.mappersManager.getMapper(
            Workspace.__name__).find(name)
        if not workspace:
            raise WorkspaceException(
                ("Error loading workspace.\n"
                 "You should try opening faraday "
                 "with the '--update' option"))
        self.setActiveWorkspace(workspace)
        notification_center.workspaceChanged(
            workspace, self.getWorkspaceType(name))
        notification_center.workspaceLoad(workspace.getHosts())
        self.changesManager.watch(self.mappersManager, dbConnector)
        return workspace

    def closeWorkspace(self):
        self.changesManager.unwatch()

    def removeWorkspace(self, name):
        if name in self.getWorkspacesNames():
            return self.dbManager.removeDb(name)

    def setActiveWorkspace(self, workspace):
        self.active_workspace = workspace

    def getActiveWorkspace(self):
        return self.active_workspace

    def workspaceExists(self, name):
        return self.dbManager.connectorExists(name)

    def resource(self):
        self.dbManager.reloadConfig()

    def isActive(self, name):
        return self.active_workspace.getName() == name

    def getWorkspaceType(self, name):
        return self._dbTypeToNamedType(self.dbManager.getDbType(name))

    def _dbTypeToNamedType(self, dbtype):
        if dbtype == DBTYPE.COUCHDB:
            return 'CouchDB'

    def namedTypeToDbType(self, name):
        if name == 'CouchDB':
            return DBTYPE.COUCHDB

    def getAvailableWorkspaceTypes(self):
        return [self._dbTypeToNamedType(dbtype) for
                dbtype in self.dbManager.getAvailableDBs()]

    def isWorkspaceNameValid(self, ws_name):
        """Returns True if the ws_name is valid, else if it's not"""
        letters_or_numbers = r"^[a-z][a-z0-9\_\$()\+\-\/]*$"
        regex_name = re.match(letters_or_numbers, ws_name)
        if regex_name and regex_name.string not in CONST_BLACKDBS:
            return True
        else:
            return False
