#!/usr/bin/python3
import json
import os
import sys
from argparse import ArgumentParser

import requests as requests
import yaml

github_user = os.getenv('GITHUB_USER')
github_token = os.getenv('GITHUB_TOKEN')
default_headers = {
    'Authorization': f'token {github_token}'
}
bad_statuses = [400, 401, 403, 404, 415, 422]


def read_yaml_file(path, org=None, endpoint=None, repo_name=None):
    if endpoint in ['manage_collaborators', 'branch_protection', 'options', 'topics']:
        path += f'/{org}/repositories/{repo_name}.yml'
    if endpoint in ['teams']:
        path += f'/{org}/teams/members.yml'
    if endpoint in ['members']:
        path += f'/{org}/people/members.yml'
    with open(path, 'r') as file:
        data = yaml.safe_load(file)
    return data


def update_topics(github_api, owner, repo_name, repo):
    headers = {**default_headers, **{'Accept': 'application/vnd.github.mercy-preview+json'}}
    output = ''
    res = requests.put(
        f'{github_api}/repos/{owner}/{repo_name}/topics',
        json={'names': repo[repo_name]['topics']},
        headers=headers,
        timeout=15)
    if res.status_code in bad_statuses:
        output += f'options change not applied: {res.status_code}, error is: {res.text}\n'
    return print(output, file=sys.stderr)


def update_options(github_api, owner, repo_name, repo):
    output = ''
    options = repo[repo_name]
    options.update({'name': repo_name})
    res = requests.patch(
        f'{github_api}/repos/{owner}/{repo_name}',
        json=options,
        headers=default_headers,
        timeout=15)
    if res.status_code in bad_statuses:
        output += f'options change not applied: {res.status_code}, error is: {res.text}\n'
    return print(output, file=sys.stderr)


def manage_collaborators(github_api, owner, repo_name, repo):
    output = ''
    collaborators = repo[repo_name]['collaborators']
    teams = repo[repo_name]['teams']
    for permission, users in collaborators.items():
        if not users:
            continue
        for user in users:
            res = requests.put(
                f'{github_api}/repos/{owner}/{repo_name}/collaborators/{user}',
                json={'permission': permission},
                headers=default_headers,
                timeout=15)
            if res.status_code in bad_statuses:
                output += f'user {user} not created: {res.status_code}, error is: {res.text}\n'
    for permission, teams in teams.items():
        if not teams:
            continue
        for team in teams:
            res = requests.put(
                f'{github_api}/orgs/{owner}/teams/{team}/repos/{owner}/{repo_name}',
                json={'permission': permission},
                headers=default_headers,
                timeout=15)
            if res.status_code in bad_statuses:
                output += f'repo not added to team: {team}: {res.status_code}, error is: {res.text}\n'
    return print(output, file=sys.stderr)


def update_branch_protection(github_api, owner, repo_name, repo):
    headers = {**default_headers, **{'Accept': 'application/vnd.github.luke-cage-preview+json'}}
    output = ''
    rules = repo[repo_name]['protection_rules']
    if isinstance(rules, str):
        rules = {repo[repo_name]['default_branch']: read_yaml_file(f'./templates/{rules}.yml')}
    branch_name = list(rules)[0]
    if 'who_can_push' in rules[branch_name]:
        rules[branch_name]['restrictions'] = rules[branch_name].pop('who_can_push')
    res = requests.put(
        f'{github_api}/repos/{owner}/{repo_name}/branches/{branch_name}/protection',
        json=rules[branch_name],
        headers=headers,
        timeout=15)
    if res.status_code in bad_statuses:
        output += f'branch protection rule not applied: {res.status_code}, error is: {res.text}\n'
    return print(output, file=sys.stderr)


def update_teams(github_api, owner, new_teams):
    output = ''
    res = requests.get(
        f'{github_api}/orgs/{owner}/teams',
        headers=default_headers,
        timeout=15)
    if res.status_code not in bad_statuses:
        teams = json.loads(res.text)
        for team in teams:
            members_to_add = new_teams['teams'][team['name']]

            current_members = []
            res = requests.get(
                f'{github_api}/orgs/{owner}/teams/{team["slug"]}/members?role=member',
                headers=default_headers,
                timeout=15)
            if res.status_code not in bad_statuses:
                members = json.loads(res.text)
                for member in members:
                    current_members.append(member['login'])
            else:
                output += f'request not succeeded: {res.status_code}, error is: {res.text}\n'

            current_maintainers = []
            res = requests.get(
                f'{github_api}/orgs/{owner}/teams/{team["slug"]}/members?role=maintainer',
                headers=default_headers,
                timeout=15)
            if res.status_code not in bad_statuses:
                maintainers = json.loads(res.text)
                for maintainer in maintainers:
                    current_maintainers.append(maintainer['login'])
            else:
                output += f'request not succeeded: {res.status_code}, error is: {res.text}\n'

            for login in members_to_add['member']:
                if current_members and login not in current_members:
                    res = requests.put(
                        f'{github_api}/orgs/{owner}/teams/{team["slug"]}/memberships/{login}',
                        json={'role': 'member'},
                        headers=default_headers,
                        timeout=15
                    )
                    if res.status_code in bad_statuses:
                        output += f'membership not updated: {res.status_code}, error is: {res.text}\n'
            for login in members_to_add['maintainer']:
                if current_maintainers and login not in current_maintainers:
                    res = requests.put(
                        f'{github_api}/orgs/{owner}/teams/{team["slug"]}/memberships/{login}',
                        json={'role': 'maintainer'},
                        headers=default_headers,
                        timeout=15)
                    if res.status_code in bad_statuses:
                        output += f'membership not updated: {res.status_code}, error is: {res.text}\n'
    else:
        output += f'request not succeeded: {res.status_code}, error is: {res.text}\n'
    return print(output, file=sys.stderr)


def update_org_members(github_api, owner, new_people):
    output = ''
    current_members = []
    res = requests.get(
        f'{github_api}/orgs/{owner}/members',
        headers=default_headers,
        timeout=15)
    org_members = json.loads(res.text)
    if res.status_code not in bad_statuses:
        for member in org_members:
            current_members.append(member['login'])
        for person in new_people['users']:
            if person['login'] not in current_members:
                res = requests.get(
                    f'{github_api}/users/{person["login"]}',
                    headers=default_headers,
                    timeout=15)
                if res.status_code not in bad_statuses:
                    user_id = json.loads(res.text)['id']
                    res = requests.post(
                        f'{github_api}/orgs/{owner}/invitations',
                        json={'invitee_id': user_id},
                        headers=default_headers,
                        timeout=15)
                    if res.status_code in bad_statuses:
                        output += f'invite not send for {person["login"]}' \
                                  f' status code: {res.status_code},' \
                                  f' error is: {res.text}\n'
                else:
                    output += f'request not succeeded: {res.status_code},' \
                              f' error is: {res.text}\n'
    else:
        output += f'request not succeeded: {res.status_code}, error is: {res.text}\n'
    return print(output, file=sys.stderr)


if __name__ == '__main__':
    args_parser = ArgumentParser(prog='github_api', description='Multi-purpose github api script')
    args_parser.add_argument('--github_api_url', help='Github api base path', default='https://api.github.com')
    args_parser.add_argument('--endpoint', help='Selected github endpoint')
    args_parser.add_argument('--org', help='Repo owner')
    args_parser.add_argument('--repo', help='Repo data')
    args_parser.add_argument('--root', help='Root directory to fetch files', default='../orgs')
    args = args_parser.parse_args()
    if args.endpoint == 'manage_collaborators':
        manage_collaborators(
            github_api=args.github_api_url,
            owner=args.org,
            repo_name=args.repo,
            repo=read_yaml_file(path=args.root, org=args.org, repo_name=args.repo, endpoint=args.endpoint)
        )
    if args.endpoint == 'branch_protection':
        update_branch_protection(
            github_api=args.github_api_url,
            owner=args.org,
            repo_name=args.repo,
            repo=read_yaml_file(path=args.root, org=args.org, repo_name=args.repo, endpoint=args.endpoint)
        )
    if args.endpoint == 'options':
        update_options(
            github_api=args.github_api_url,
            owner=args.org,
            repo_name=args.repo,
            repo=read_yaml_file(path=args.root, org=args.org, repo_name=args.repo, endpoint=args.endpoint)
        )
    if args.endpoint == 'teams':
        update_teams(
            github_api=args.github_api_url,
            owner=args.org,
            new_teams=read_yaml_file(path=args.root, org=args.org, endpoint=args.endpoint)
        )
    if args.endpoint == 'members':
        update_org_members(
            github_api=args.github_api_url,
            owner=args.org,
            new_people=read_yaml_file(path=args.root, org=args.org, endpoint=args.endpoint)
        )
    if args.endpoint == 'topics':
        update_topics(
            github_api=args.github_api_url,
            owner=args.org,
            repo_name=args.repo,
            repo=read_yaml_file(path=args.root, org=args.org, repo_name=args.repo, endpoint=args.endpoint)
        )
