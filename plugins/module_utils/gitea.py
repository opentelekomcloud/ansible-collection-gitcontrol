# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type


import json

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.opentelekomcloud.gitcontrol.plugins.module_utils.git import GitBase


REPOSITORY_UPDATABLE_ATTRIBUTES = [
    'allow_manual_merge',
    'allow_merge_commits',
    'allow_rebase',
    'allow_rebase_explicit',
    'allow_rebase_update',
    'allow_squash_merge',
    'archived',
    'autodetect_manual_merge',
    'default_branch',
    'default_delete_branch_after_merge',
    'default_merge_style',
    'description',
    'enable_prune',
    'has_issues',
    'has_projects',
    'has_pull_requests',
    'has_wiki',
    'ignore_whitespace_conflicts',
    'private',
    'template',
    'website'
]


def base_argument_spec(**kwargs):
    spec = dict(
        token=dict(type='str', required=True, no_log=True),
        api_url=dict(type='str', required=True),
    )
    spec.update(kwargs)
    return spec


class GiteaBase(GitBase):

    argument_spec = {}
    module_kwargs = {}
    _bp_templates = {}

    def __init__(self):
        self.ansible = AnsibleModule(
            base_argument_spec(**self.argument_spec),
            **self.module_kwargs
        )
        self.params = self.ansible.params
        self.module_name = self.ansible._name
        self.results = {'changed': False}
        self.exit = self.exit_json = self.ansible.exit_json
        self.fail = self.fail_json = self.ansible.fail_json

        self.api_url = self.params['api_url']
        self.errors = []
        self._users_cache = dict()

    def save_error(self, msg):
        self.ansible.log(msg)
        self.errors.append(msg)

    def _request(self, method, url, headers=None, **kwargs):
        if not headers:
            headers = dict()

        headers.update({
            'Authorization': f"token {self.params['token']}",
            'Content-Type': "application/json",
        })

        if not url.startswith('http'):
            url = f"{self.api_url}/{url}"

        return super()._request(
            method=method,
            url=url,
            headers=headers,
            **kwargs
        )

    def request(
        self, method='GET', url=None, headers=None, timeout=15,
        error_msg=None, ignore_missing=False,
        **kwargs
    ):

        body, response, info = self._request(
            method=method,
            url=url,
            headers=headers,
            timeout=timeout,
            **kwargs,
        )

        status = info['status']

        if status >= 400 and status != 404:
            if not error_msg:
                error_msg = (
                    f"API returned error on {url}"
                )
            error_data = dict(url=url)
            for key in ['url', 'msg', 'status', 'body']:
                if key in info:
                    error_data[key] = info[key]

            self.save_error(f"{error_msg}: {error_data}")
        elif status == 404 and ignore_missing:
            return None
        if status == 204:
            return response
        elif body and status < 400:
            return json.loads(body)

    def paginated_request(self, url, headers=None, timeout=15, params=None):
        if not url.startswith('http'):
            url = f"{self.api_url}/{url}"

        if not params:
            params = dict()
        total_count = 0
        fetched = 0
        page = 1
        headers['Accept'] = 'application/json'
        while True:
            content, response, info = self._request(
                method='GET',
                url=url,
                headers=headers,
                timeout=timeout,
                params=params
            )
            total_count = int(response.headers.get('X-Total-Count', 0))
            data = json.loads(content)
            if isinstance(data, list):
                for rec in data:
                    yield rec
                    fetched += 1
                if fetched == total_count:
                    return
                else:
                    page += 1
                    params['page'] = page

    def get_repo(self, owner, repo, ignore_missing=False):
        """Get repository information"""
        return self.request(
            method='GET',
            url=f"repos/{owner}/{repo}",
            error_msg=f"Repo {repo}@{owner} cannot be fetched",
            ignore_missing=ignore_missing
        )

    def create_repo(self, owner, repo, **args):
        if not args:
            args = dict()
        args['name'] = repo
        rsp = self.request(
            method='POST',
            url=f"orgs/{owner}/repos",
            json=args,
            error_msg=f"Repo {repo}@{owner} cannot be created"
        )
        return rsp

    def update_repo(self, owner, repo, **kwargs):
        """Update repository options"""
        data = dict()
        for attr in REPOSITORY_UPDATABLE_ATTRIBUTES:
            if attr in kwargs and kwargs[attr] is not None:
                data[attr] = kwargs[attr]

        rsp = self.request(
            method='PATCH',
            url=f'repos/{owner}/{repo}',
            json=data,
            error_msg=f"Repo {repo}@{owner} cannot be updated"
        )
        return rsp

    def delete_repo(self, owner, repo):
        """Delete repository"""
        rsp = self.request(
            method='DELETE',
            url=f'repos/{owner}/{repo}',
            error_msg=f"Repo {repo}@{owner} cannot be deleted"
        )
        return rsp

    def get_branch_protection(self, owner, repo, branch):
        """Get branch protection rules"""

        return self.request(
            method='GET',
            url=(f'repos/{owner}/{repo}/branch_protections/{branch}'),
            error_msg=f"Repo {repo}@{owner} branch protection cannot be updated"
        )

    def create_branch_protection(self, owner, repo, branch, target):
        """Set branch protection rules"""
        target['branch_name'] = branch

        self.request(
            method='POST',
            url=(f'repos/{owner}/{repo}/branch_protections'),
            json=target,
            error_msg=f"Repo {repo}@{owner} branch protection cannot be updated"
        )

        return True

    def update_branch_protection(self, owner, repo, branch, target):
        """Set branch protection rules"""

        self.request(
            method='PATCH',
            url=(f'repos/{owner}/{repo}/branch_protections/{branch}'),
            json=target,
            error_msg=f"Repo {repo}@{owner} branch protection cannot be updated"
        )

        return True

    def _manage_repository(self, state, current=None, check_mode=False, **kwargs):

        changed = False
        owner = kwargs.pop('owner')
        repo_name = kwargs.pop('name')
        current_repo = current if current else self.get_repo(owner, repo_name, ignore_missing=True)
        if not current_repo:
            changed = True
            if not check_mode:
                # TODO(gtema) create and update take different set of props. Deal with that here
                current_repo = self.create_repo(
                    owner, repo_name, **kwargs)
            else:
                return (changed, kwargs)

        archive = kwargs.pop('archived', False)
        if (
            current_repo
            and archive and current_repo.get('archived')
        ):
            # Do nothing for the archived repo
            return (changed, current_repo)

        if current_repo and self._is_repo_update_needed(current_repo, kwargs):
            changed = True
            if not check_mode:
                current_repo = self.update_repo(owner, repo_name, **kwargs)

        # Repository collaborator teams
        target_teams = kwargs.get('teams')
        if (
            current_repo and target_teams is not None
        ):
            (changed, teams) = self._manage_repo_teams(
                owner, repo_name, target_teams, check_mode)
            current_repo['teams'] = teams

        # Repository collaborators
        target_collaborators = kwargs.get('collaborators')
        if (
            current_repo and target_collaborators is not None
        ):
            changed = self._manage_repo_collaborators(
                owner, repo_name, target_collaborators, check_mode)

        # Branch protections

        # Branch protection should be managed after teams and collaborators
        # since it can require particular reviewer which still has no access.

        branch_protections = kwargs.pop('branch_protections', [])
        if current_repo and branch_protections is not None:
            current_repo['branch_protections'] = []
            for bp in branch_protections:
                current_bp = self.get_branch_protection(
                    owner, repo_name, bp['branch_name']
                )
                if not current_bp:
                    self.create_branch_protection(
                        owner, repo_name, bp['branch_name'], bp
                    )
                else:
                    if (
                        self._is_branch_protection_update_needed(
                            owner, repo_name, bp['branch_name'], bp, current_bp)
                    ):
                        changed = True
                        if not check_mode:
                            self.update_branch_protection(
                                owner, repo_name, bp['branch_name'], bp)
                current_repo['branch_protections'].append(bp)

        # If we need to archive - do this after updating everything else
        if (
            current_repo
            and archive and not current_repo.get('archived')
        ):
            changed = True
            if not check_mode:
                current_repo = self.update_repo(
                    owner, repo_name, archived=True)

        return (changed, current_repo)

    def _is_repo_update_needed(self, current, target):
        for attr in REPOSITORY_UPDATABLE_ATTRIBUTES:
            if attr in target and target[attr] != current.get(attr):
                return True

    def _is_branch_protection_update_needed(
        self,
        owner,
        repo,
        branch,
        target,
        current=None
    ):
        BRANCH_PROTECTION_PROPS = [
            'approvals_whitelist_teams',
            'approvals_whitelist_username',
            'block_on_official_review_requests',
            'block_on_outdated_branch',
            'block_on_rejected_reviews',
            'dismiss_stale_reviews',
            'enable_approvals_whitelist',
            'enable_merge_whitelist',
            'enable_push',
            'enable_push_whitelist',
            'enable_status_check',
            'merge_whitelist_teams',
            'merge_whitelist_usernames',
            'protected_file_patterns',
            'push_whitelist_deploy_keys',
            'push_whitelist_teams',
            'push_whitelist_usernames',
            'require_signed_commits',
            'required_approvals',
            'status_check_contexts',
            'unprotected_file_patterns'
        ]
        for prop in BRANCH_PROTECTION_PROPS:
            if prop in target and current.get(prop) != target[prop]:
                return True
        return False

    def get_repo_teams(self, owner, repo):
        """Get repo teams"""
        rsp = self.request(
            method='GET',
            url=(f"repos/{owner}/{repo}/teams"),
            error_msg=f"Cannot fetch team {owner}/{repo} teams"
        )

        return rsp

    def delete_repo_team_access(self, owner, repo, team):
        """Delete team from repo collaborators"""
        self.request(
            method='DELETE',
            url=f"repos/{owner}/{repo}/teams/{team}",
            error_msg=f"Cannot delete team {team}@{owner}/{repo} access"
        )

    def add_repo_team_access(self, owner, repo, team):
        """Add team as repo collaborators"""
        self.request(
            method='PUT',
            url=f"repos/{owner}/{repo}/teams/{team}",
            error_msg=f"Cannot add team {team}@{owner}/{repo} access"
        )

    def _manage_repo_teams(
        self, owner, repo_name, target, check_mode=False
    ):
        """Manage repository teams"""
        changed = False
        teams = None
        current_teams = set([x['name'] for x in
                            self.get_repo_teams(owner, repo_name) or []])
        target_teams = set(target + ['Owners'])
        for old_team in current_teams.difference(target_teams):
            changed = True
            if not check_mode:
                self.delete_repo_team_access(owner, repo_name, old_team)
        for new_team in target_teams.difference(current_teams):
            changed = True
            if not check_mode:
                self.add_repo_team_access(owner, repo_name, new_team)
        teams = set([x['name'] for x in
                    self.get_repo_teams(owner, repo_name) or []])
        return (changed, teams)

    def get_repo_collaborators(self, owner, repo):
        """Get repo collaborators"""
        rsp = self.request(
            method='GET',
            url=(f"repos/{owner}/{repo}/collaborators"),
            error_msg=f"Cannot fetch team {owner}/{repo} collaborators"
        )

        return rsp

    def add_repo_collaborator(self, owner, repo, login, permission):
        """Add repo collaborator"""
        rsp = self.request(
            method='PUT',
            url=(f"repos/{owner}/{repo}/collaborators/{login}"),
            json={"permission": permission},
            error_msg=f"Cannot add collaborator to  {owner}/{repo}"
        )

        return rsp

    def remove_repo_collaborator(self, owner, repo, login):
        """Remove repo collaborator"""
        rsp = self.request(
            method='DELETE',
            url=(f"repos/{owner}/{repo}/collaborators/{login}"),
            error_msg=f"Cannot add collaborator to  {owner}/{repo}"
        )

        return rsp

    def get_repo_collaborator_permission(self, owner, repo, login):
        """Get repo collaborators"""
        rsp = self.request(
            method='GET',
            url=(f"repos/{owner}/{repo}/collaborators/{login}/permission"),
            error_msg=f"Cannot fetch team {owner}/{repo} collaborators"
        )

        return rsp

    def _manage_repo_collaborators(
        self, owner, repo_name, target, check_mode=False
    ):
        """Manage repository collaborators"""
        changed = False
        current_collaborators = {x['login']: 1 for x in
                                 self.get_repo_collaborators(owner, repo_name) or []}
        target_collaborators = {x['username']: x['permission'] for x in
                                target}
        for login, permission in target_collaborators.items():
            if login not in current_collaborators:
                changed = True
                if not check_mode:
                    self.add_repo_collaborator(
                        owner, repo_name, login, permission
                    )
            else:
                current = self.get_repo_collaborator_permission(
                    owner, repo_name, login
                )
                if current["permission"] != permission:
                    changed = True
                    if not check_mode:
                        self.add_repo_collaborator(
                            owner, repo_name, login, permission
                        )

        for login in current_collaborators.keys():
            if login not in target_collaborators:
                changed = True
                if not check_mode:
                    self.delete_repo_collaborator(
                        owner, repo_name, login
                    )

        return changed
