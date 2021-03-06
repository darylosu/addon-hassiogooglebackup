import googleapiclient.http
from google_auth_oauthlib.flow import InstalledAppFlow
from google_auth_oauthlib.flow import Flow
from oauth2client.client import GoogleCredentials
from googleapiclient.discovery import build
from httplib2 import Http

from django.conf import settings
import os
import json
import glob
import ntpath
import pprint

OAUTH2_SCOPE = 'https://www.googleapis.com/auth/drive.file'

CLIENT_SECRET = os.path.join(settings.BASE_DIR, "client_secret.json")
TOKEN = os.path.join(settings.DATA_PATH, "token.json")
CONFIG_FILE = os.path.join(settings.DATA_PATH, "options.json")


def getOptions():
    with open(CONFIG_FILE) as f:
        options = json.load(f)
    return options

def getFlowFromClientSecret():
    flow = InstalledAppFlow.from_client_secrets_file(
        CLIENT_SECRET,
        scopes=[OAUTH2_SCOPE])
    return flow

def getFlowFromClientSecret_Step2(saved_state):
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRET,
        scopes=[OAUTH2_SCOPE],
        state=saved_state)
    return flow

def requestAuthorization():

    flow = getFlowFromClientSecret()

    # Indicate where the API server will redirect the user after the user completes
    # the authorization flow. The redirect URI is required.
    flow.redirect_uri = "urn:ietf:wg:oauth:2.0:oob"

    # Generate URL for request to Google's OAuth 2.0 server.
    # Use kwargs to set optional request parameters.
    authorization_url, state = flow.authorization_url(
        # Enable offline access so that you can refresh an access token without
        # re-prompting the user for permission. Recommended for web server apps.
        access_type='offline',
        # Enable incremental authorization. Recommended as a best practice.
        include_granted_scopes='true')

    return authorization_url, state

def fetchAndSaveTokens(saved_state, redirect_uri, authorization_response, authorizationCode):

    flow = getFlowFromClientSecret_Step2(saved_state)
    # flow.redirect_uri = redirect_uri
    flow.redirect_uri = "urn:ietf:wg:oauth:2.0:oob"

    flow.fetch_token(code=authorizationCode)

    # Store the credentials for later use by REST service
    credentials = flow.credentials
    tokens = {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }

    with open(TOKEN, 'w') as outfile:
        json.dump(tokens, outfile)

def getDriveService(user_agent):

    with open(TOKEN) as f:
        creds = json.load(f)

    credentials = GoogleCredentials(None,creds["client_id"],creds["client_secret"],
                                          creds["refresh_token"],None,"https://accounts.google.com/o/oauth2/token",user_agent)
    http = credentials.authorize(Http())
    credentials.refresh(http)
    drive_service = build('drive', 'v3', http)

    return drive_service

def alreadyBackedUp(fileName, backupDirID, drive_service):

    shortFileName = ntpath.basename(fileName)

    # Search for given file in Google Drive Directory
    results = drive_service.files().list(
        q="name='" + shortFileName + "' and '" + backupDirID + "' in parents and trashed = false",
        spaces='drive',
        fields="files(id, name)").execute()
    items = results.get('files', [])

    return len(items) > 0

def backupFile(fileName, backupDirID, drive_service):

    print("Backing up " + fileName + " to " + backupDirID)

    shortFileName = ntpath.basename(fileName)

    # Metadata about the file.
    # Only supported file type right now is tar file.
    MIMETYPE = 'application/tar'
    TITLE = 'Hassio Snapshot'
    DESCRIPTION = 'Hassio Snapshot backup copy'

    media_body = googleapiclient.http.MediaFileUpload(
        fileName,
        mimetype=MIMETYPE,
        resumable=True
    )

    body = {
        'name': shortFileName,
        'title': TITLE,
        'description': DESCRIPTION,
        'parents': [backupDirID]
    }

    new_file = drive_service.files().create(
    body=body, media_body=media_body).execute()
    pprint.pprint(new_file)

def backupFiles(fromPattern, backupDirID, user_agent):

    drive_service = getDriveService(user_agent)

    fileCount = 0
    alreadyCount = 0
    backedUpCount = 0
    for file in glob.glob(fromPattern):
        fileCount += 1
        if alreadyBackedUp(file, backupDirID, drive_service):
            alreadyCount += 1
        else:
            backupFile(file, backupDirID, drive_service)
            backedUpCount += 1
    result = {'fromPattern': fromPattern,
                'backupDirID': backupDirID,
                'fileCount': fileCount,
                'alreadyCount': alreadyCount,
                'backedUpCount': backedUpCount}

    return result