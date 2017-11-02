#!/usr/bin/env python
# travis-activate.py
# Dan Wallach <dwallach@rice.edu>

import requests
import json
import re
import subprocess

# see installation and usage instructions in README.md

travisToken = subprocess.check_output(["git", "config", "--global", "travis.token"]).rstrip()

# and we're going to need the name of your GitHub "project" in which all your
# students' work lives

githubProject = 'iesdonana'

# and since there are going to be lots of repos that we don't necessarily care about, let's
# have a predicate to match the ones we *do* care about

repoRegex = ".*-.*"

# API documentation: https://developer.travis-ci.org/ 
# (for the V3 APIs, which are mostly what we're using here)

requestHeaders = {
    "User-Agent": "TravisActivate/1.0",
    "Authorization": "token \"" + travisToken + "\"",
    "Accept": "application/vnd.travis-ci.2+json"
}

requestHeadersV3 = {
    "User-Agent": "TravisActivate/1.0",
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Travis-API-Version": "3",
    "Authorization": "token " + travisToken
}

# Before we begin with the specific repos, we're going to ask Travis-CI to synchronize its
# view of the repositories from GitHub. To do that, we need to get the 'id' of the user,
# since that's part of the subsequent 'sync' request.

userInfo = requests.get('https://api.travis-ci.com/user', headers = requestHeadersV3) 

if userInfo.status_code != 200:
    print "Failed to load user info from Travis: " + userInfo.content
    exit(1)

userId = userInfo.json()['id']

syncPost = requests.post('https://api.travis-ci.com/user/%d/sync' % userId, headers = requestHeadersV3)

if syncPost.status_code != 200:
    print "Requested sync from GitHub to Travis; Travis responded: \"%s\"" % syncPost.json()['error_message']
else:
    print "Requested sync from GitHub to Travis."

foundLastRepo = False
repoList = []
limit = 100    # make this bigger, and nothing happens
offset = 0

while not foundLastRepo:
    print "Fetching repos: %d -> %d" % (offset, offset+limit)
    repoDump = requests.get('https://api.travis-ci.com/owner/%s/repos' % githubProject,
                            headers = requestHeadersV3,
                            params = {'limit': limit, 'offset': offset})
    
    if repoDump.status_code != 200:
        # hopefuly human-readable text complaining about the problem
        print "Failed to load repo list from Travis: " + repoList.content 
        exit(1)
    
    # Before we can deal with the data structure here, we have to collect all of the
    # entries. Travis-CI will only give us 100 of them at a time, even if you explicitly
    # set a larger limit parameter. Because reasons. 
        
    repoList = repoList + repoDump.json()['repositories']
    pagination = repoDump.json()['@pagination']
    if pagination['is_last']:
        foundLastRepo = True
    else:
        limit = pagination['next']['limit']
        offset = pagination['next']['offset']
        
# each entry in the list now looks something like this: {
# "slug": "RiceComp215/comp215-week01-intro-2017-studentName",
# "name": "comp215-week01-intro-2017-studentName",
# "github_language": null,
# "default_branch": {
#     "@representation": "minimal",
#     "@href": "/repo/3205265/branch/master",
#     "@type": "branch",
#     "name": "master"
# },
# "owner": {
#     "login": "RiceComp215",
#     "@href": "/org/111720",
#     "@type": "organization",
#     "id": 111720
# },
# "private": true,
# "id": 3205265,
# "@permissions": {
#     "activate": true,
#     "star": true,
#     "read": true,
#     "create_request": true,
#     "create_cron": true,
#     "delete_key_pair": true,
#     "admin": true,
#     "unstar": true,
#     "create_key_pair": true,
#     "deactivate": true,
#     "create_env_var": true
# },
# "@href": "/repo/3205265",
# "@representation": "standard",
# "starred": false,
# "active": false,
# "@type": "repository",
# "description": "comp215-week01-intro-2017-studentName created by GitHub Classroom" }

################

# For the requests we're about to make, we need to send these requests to Travis.

desiredSettings = {
    "settings": {
        "builds_only_with_travis_yml": True,
        "build_pushes": True,
        "build_pull_requests": True,
        "maximum_number_of_builds": 1
    }
}

buildRequest = {
    "request": {
        "branch": "master"
    }
}

#
# Note: the Travis-CI API places a limit on the number of rebuilds that can
# be requested in a given amount of time. It's more important that we do
# all the other work, activations, etc., so that's why there are two separate
# loops here. Important work first.
#
repoMatcher = re.compile(repoRegex)
print "---------------------"
repoListFiltered = [x for x in repoList if repoMatcher.search(x['slug'])]
print "Total repos found: %d of %d matching %s" % (len(repoListFiltered), len(repoList), repoRegex)

repoListInactive = [x for x in repoListFiltered if not x['active']]

if len(repoListInactive) == 0:
    print "Every repo is active, nothing to do."
    exit(0);

print "Total repos needing activation: %d" % len(repoListInactive)

for repo in repoListInactive:
    id = str(repo['id'])
    print "Activating: " + repo['slug']

    requests.post('https://api.travis-ci.com/repo/%s/activate' % id,
                  headers = requestHeadersV3,
                  data = json.dumps(buildRequest))

    requests.patch('https://api.travis-ci.com/repos/%s/settings' % id,
                   headers = requestHeaders,
                   data = json.dumps(desiredSettings))

print "---------------------"

for repo in repoListInactive:
    id = str(repo['id'])
    print "Requesting rebuild: " + repo['slug']

    requests.post('https://api.travis-ci.com/repo/%s/requests' % id,
                  headers = requestHeadersV3,
                  data = json.dumps(buildRequest))
