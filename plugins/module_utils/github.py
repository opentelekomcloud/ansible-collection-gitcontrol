# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type


import os

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.basic import missing_required_lib
from ansible_collections.opentelekomcloud.gitcontrol.plugins.module_utils.git import GitBase


QUERY_MEMBERS = '''
query members(
  $owner: String!
  $memberCursor: String
) {
  organization(login: $owner) {
    membersWithRole(first: 100, after: $memberCursor) {
      edges {
        role
        node {
          login
        }
      }
      pageInfo {
        hasNextPage
        endCursor
      }
    }
  }
}
'''


def base_argument_spec(**kwargs):
    spec = dict(
        root=dict(type='str', required=False),
        token=dict(type='str', required=True, no_log=True),
        github_url=dict(type='str', default='https://api.github.com')
    )
    spec.update(kwargs)
    return spec


class GitHubBase(GitBase):

    argument_spec = {}
    module_kwargs = {}
    _bp_templates = {}

    def __init__(self):
        self.ansible = AnsibleModule(
            base_argument_spec(**self.argument_spec),
            **self.module_kwargs)
        self.params = self.ansible.params
        self.module_name = self.ansible._name
        self.results = {'changed': False}
        self.exit = self.exit_json = self.ansible.exit_json
        self.fail = self.fail_json = self.ansible.fail_json

        self.gh_url = self.params['github_url']
        self.errors = []
        self._users_cache = dict()

        if not HAS_REQUESTS:
            self.fail_json(msg=missing_required_lib('requests'))

        if not HAS_YAML:
            self.fail_json(msg=missing_required_lib('yaml'))

    def save_error(self, msg):
        self.ansible.log(msg)
        self.errors.append(msg)

    def get_config(self):
        output = {}
        for root, dirs, files in os.walk(self.params['root'] + '/orgs'):
            for file in [x for x in files if x.endswith(('.yml', '.yaml'))]:
                current_root = os.path.basename(root)
                a_yaml_file = open(os.path.join(root, file))
                parsed_yaml_file = yaml.safe_load(a_yaml_file)
                parent = os.path.basename(os.path.abspath(os.path.join(root, os.pardir)))
                if parent in output:
                    if current_root in output[parent]:
                        output[parent][current_root].update(parsed_yaml_file)
                    else:
                        output[parent].update({current_root: parsed_yaml_file})
                else:
                    output.update({parent: {current_root: parsed_yaml_file}})
        return output

    def _prepare_graphql_query(self, query, variables):
        data = {
            'query': query,
            'variables': variables,
        }
        return data

    def get_teams(self):
        teams = dict()
        conf = self.get_config()
        for owner, val in conf.items():
            teams[owner] = dict()
            teams[owner]['present'] = self.read_yaml_file(
                path=(f"{self.params['root']}/orgs/{owner}/"
                      "teams/members.yml")
            )
            teams[owner]['dismissed'] = self.read_yaml_file(
                path=(f"{self.params['root']}/orgs/{owner}/"
                      "teams/dismissed_members.yml")
            )

        return teams

    def get_members(self):
        members = dict()
        conf = self.get_config()
        for owner, val in conf.items():
            members[owner] = dict()
            members[owner]['present'] = self.read_yaml_file(

                path=(f"{self.params['root']}/orgs/{owner}/"
                      "people/members.yml")
            )
            members[owner]['dismissed'] = self.read_yaml_file(
                path=(f"{self.params['root']}/orgs/{owner}/"
                      "people/dismissed_members.yml")
            )

        return members

    def get_branch_protections(self, name):
        if name not in self._bp_templates:
            self._bp_templates[name] = self.read_yaml_file(
                f"{self.params['root']}/templates/{name}.yml")
        tmpl = self._bp_templates.get(name)
        if tmpl:
            if 'who_can_push' in tmpl:
                tmpl['restrictions'] = tmpl.pop('who_can_push')

        return tmpl

    def read_yaml_file(self, path, org=None, endpoint=None, repo_name=None):
        if endpoint in ['manage_collaborators', 'branch_protection', 'options', 'topics']:
            path += f'/{org}/repositories/{repo_name}.yml'
        if endpoint in ['teams']:
            path += f'/{org}/teams/members.yml'
        if endpoint in ['members']:
            path += f'/{org}/people/members.yml'
        with open(path, 'r') as file:
            data = yaml.safe_load(file)
        return data

    def request(self, method='GET', url=None, headers=None, timeout=15,
                error_msg=None, **kwargs):
        if not headers:
            headers = dict()

        headers.update({
            'Authorization': f"token {self.params['token']}"
        })
        if 'Accept' not in headers:
            headers['Accept'] = 'application/vnd.github.v3+json'

        if not url.startswith('http'):
            url = f"{self.gh_url}/{url}"

        response = requests.request(
            method, url, headers=headers, timeout=timeout, **kwargs)

        if response.status_code >= 400 and response.status_code != 404:
            if not error_msg:
                error_msg = (
                    f"API returned error on {url}"
                )
                self.save_error(f"{error_msg}: {response.text}")

        return response

    def paginated_request(self, url, headers=None, timeout=15, **kwargs):
        while url:
            response = self.request(
                method='GET',
                url=url, headers=headers, timeout=timeout, **kwargs
            )
            url = response.links.get("next", {}).get("url")
            for item in response.json():
                yield item

    def get_owner_teams(self, owner):
        """Get Team information"""
        rsp = self.request(
            method='GET',
            url=f'orgs/{owner}/teams',
        )
        if rsp.status_code not in [200]:
            self.save_error(
                f'Cannot fetch organization {owner} teams: {rsp.text}')

        return rsp.json()

    def create_team(
        self, owner, name, description=None, privacy=None,
        parent=None, maintainers=None
    ):
        """Create Team"""
        body = dict(
            name=name,
            description=description,
            privacy=privacy,
            parent=parent,
            maintainers=maintainers
        )

        rsp = self.request(
            method='POST',
            url=f"orgs/{owner}/teams",
            json=body,
        )
        if rsp.status_code not in [201]:
            self.save_error(f"Cannot create team {name}: {rsp.text}")
        else:
            return rsp.json()

    def update_team(
        self, owner, team, **kwargs
    ):
        """Update team properties
        """
        body = dict()
        if 'name' in kwargs:
            body['name'] = kwargs['name']
        if 'description' in kwargs:
            body['description'] = kwargs['description']
        if 'privacy' in kwargs:
            body['privacy'] = kwargs['privacy']

        rsp = self.request(
            method='PATCH',
            url=f"orgs/{owner}/teams/{team}",
            json=body,
        )
        if rsp.status_code not in [200, 201]:
            self.save_error(f"Cannot update team {team}@{owner}: {rsp.text}")
        else:
            return True

    def get_team_members(self, owner, team, role='maintainer'):
        """Get team members"""
        rsp = self.request(
            method='GET',
            url=(f"orgs/{owner}/"
                 f"teams/{team}/members?role={role}"),
        )
        if rsp.status_code not in [200]:
            self.save_error(
                f"Cannot fetch team {team}@{owner} {role}s: {rsp.text}")

        return rsp.json()

    def get_team_repo_permissions(self, owner, team, repo):
        """Get team permissions on a repo"""
        headers = dict(
            Accept='application/vnd.github.v3.repository+json'
        )
        rsp = self.request(
            method='GET',
            url=(f"orgs/{owner}/"
                 f"teams/{team}/projects/{owner}/{repo}"),
            headers=headers
        )
        if rsp.status_code not in [200]:
            self.save_error(
                f"Cannot fetch team {team}@{owner}/{repo} permissions: {rsp.text}")

        return rsp.json()

    def update_team_repo_permissions(self, owner, team, repo, priv):
        """Set team permissions on a repo"""
        rsp = self.request(
            method='PUT',
            url=(f"orgs/{owner}/"
                 f"teams/{team}/repos/{owner}/{repo}"),
            json={'permission': priv}
        )
        if rsp.status_code not in [200, 201, 202, 204]:
            self.save_error(
                f"Cannot update team {team}@{owner}/{repo} permissions: {rsp.text}")

        return True

    def delete_team_repo_access(self, owner, team, repo):
        """Delete repo access from team"""
        rsp = self.request(
            method='DELETE',
            url=(f"orgs/{owner}/"
                 f"teams/{team}/repos/{owner}/{repo}"),
        )
        if rsp.status_code not in [200, 201, 202, 204]:
            self.save_error(
                f"Cannot delete team {team}@{owner}/{repo} access: {rsp.text}")

        return True

    def set_team_member(self, owner, team, login, role='member'):
        """Add user into the team
        :returns: True if operation succeed, False otherwise
        """
        rsp = self.request(
            method='PUT',
            url=(f"orgs/{owner}/"
                 f"teams/{team}/memberships/{login}"),
            json={'role': role},
        )
        if rsp.status_code not in [200, 201, 202]:
            self.save_error(
                f"Membership {login}@{team} not updated: {rsp.text}")
            return False

        return True

    def get_org_members(self, owner):
        """Get organization members"""
        return self.paginated_request(
            url=f'orgs/{owner}/members',
            error_msg="Cannot fetch organizaition members"
        )

    def update_org_membership(self, owner, username, role):
        """Set organization membership for the user"""
        rsp = self.request(
            method="PUT",
            url=f"orgs/{owner}/memberships/{username}",
            json={"role": role},
            error_msg=f"Membership for user {username} not updated"
        )

        if rsp.status_code not in [201, 202]:
            return False

        return True

    def get_org_invitations(self, owner):
        """List existing user invitations
        """
        return self.paginated_request(
            url=f"orgs/{owner}/invitations",
            error_msg=f"Cannot fetch invitations for {owner}"
        )

    def create_organization_invitation(self, owner, user, role='direct_member'):
        """Send Invitation to join the org"""
        rsp = self.request(
            method='POST',
            url=f"orgs/{owner}/invitations",
            json={'invitee_id': user['id'], 'role': role},
        )
        if rsp.status_code not in [201, 202]:
            self.save_error(f"Member {user['id']} not invited: {rsp.text}")
            return False

        return True

    def delete_org_invitation(self, owner, id):
        """Cancel organization invitation"""
        rsp = self.request(
            method='DELETE',
            url=f"orgs/{owner}/invitations/{id}",
            error_msg=f"Organization invite {owner}/{id} not cacnelled"
        )
        if rsp.status_code >= 400:
            return False

        return True

    def delete_org_member(self, owner, login):
        """Remove organization member"""
        rsp = self.request(
            method='DELETE',
            url=f"orgs/{owner}/members/{login}",
            error_msg=f"Organization member {owner}/{login} not removed"
        )
        if rsp.status_code >= 400:
            return False

        return True

    def get_user(self, login):
        """Get user info"""
        user = None
        if login not in self._users_cache:
            rsp = self.request(
                method='GET',
                url=f"users/{login}",
            )
            if rsp.status_code == 200:
                user = rsp.json()
                self._users_cache[login] = user
        user = self._users_cache.get(login)
        return user

    def get_repo(self, owner, repo, ignore_missing=False):
        """Get repository information"""
        rsp = self.request(
            method='GET',
            url=f"repos/{owner}/{repo}",
        )
        if rsp.status_code not in [200]:
            if ignore_missing and rsp.status_code == 404:
                return None
            self.save_error(
                f"Repo {repo}@{owner} cannot be fetched: {rsp.text}")
            return None

        return rsp.json()

    def create_repo(self, owner, repo, **args):
        if not args:
            args = dict()
        args['name'] = repo
        rsp = self.request(
            method='POST',
            url=f"orgs/{owner}/repos",
            json=args
        )
        if rsp.status_code not in [200, 201, 202]:
            self.save_error(
                f"Repo {repo}@{owner} cannot be created: {rsp.text}")
            return None

        return rsp.json()

    def update_repo(self, owner, repo, **kwargs):
        """Update repository options"""
        rsp = self.request(
            method='PATCH',
            url=f'repos/{owner}/{repo}',
            json=kwargs,
        )
        if rsp.status_code not in [200, 201, 202]:
            self.save_error(
                f"Repo {repo}@{owner} cannot be updated: {rsp.text}")
            return None

        return rsp.json()

    def get_repo_topics(self, owner, repo):
        """Get repository topics"""
        headers = dict(
            Accept='application/vnd.github.mercy-preview+json'
        )

        rsp = self.request(
            method='GET',
            url=f'repos/{owner}/{repo}/topics',
            headers=headers,
        )
        if rsp.status_code not in [200, 201, 202]:
            self.save_error(
                f"Repo {repo}@{owner} topics cannot be updated: {rsp.text}")
            return None

        return rsp.json()['names']

    def update_repo_topics(self, owner, repo, topics):
        """Set repository topics"""
        headers = dict(
            Accept='application/vnd.github.mercy-preview+json'
        )

        rsp = self.request(
            method='PUT',
            url=f'repos/{owner}/{repo}/topics',
            headers=headers,
            json={'names': topics},
        )
        if rsp.status_code not in [200, 201, 202]:
            self.save_error(
                f"Repo {repo}@{owner} topics cannot be updated: {rsp.text}")
            return None

        return rsp.json()

    def get_branch_protection(self, owner, repo, branch):
        """Get branch protection rules"""
        headers = dict(
            Accept='application/vnd.github.luke-cage-preview+json',
        )

        rsp = self.request(
            method='GET',
            url=(f'repos/{owner}/{repo}/branches/{branch}/protection'),
            headers=headers,
        )
        if rsp.status_code not in [200, 201, 202, 404]:
            self.save_error(
                f"Repo {repo}@{owner} branch protection cannot be fetched"
                f": {rsp.text}")
            return None

        return rsp.json()

    def update_branch_protection(self, owner, repo, branch, target):
        """Set branch protection rules"""
        headers = dict(
            Accept='application/vnd.github.luke-cage-preview+json',
        )

        rsp = self.request(
            method='PUT',
            url=(f'repos/{owner}/{repo}/branches/{branch}/protection'),
            headers=headers,
            json=target
        )
        if rsp.status_code not in [200, 201, 202]:
            self.save_error(
                f"Repo {repo}@{owner} branch protection cannot be updated"
                f": {rsp.text}")
            return None

        return True

    def get_repo_teams(self, owner, repo):
        """Get repo teams"""
        headers = dict(
            Accept='application/vnd.github.v3+json'
        )
        rsp = self.request(
            method='GET',
            url=(f"repos/{owner}/{repo}/teams"),
            headers=headers
        )
        if rsp.status_code not in [200]:
            self.save_error(
                f"Cannot fetch team {owner}/{repo} teams: {rsp.text}")

        return rsp.json()

    def get_repo_collaborators(self, owner, repo, affiliation='direct'):
        """Get repo collaborators"""
        headers = dict(
            Accept='application/vnd.github.v3+json'
        )
        rsp = self.request(
            method='GET',
            url=(f"repos/{owner}/{repo}/collaborators"),
            params={
                'affiliation': affiliation
            },
            headers=headers
        )
        if rsp.status_code not in [200]:
            self.save_error(
                f"Cannot fetch team {owner}/{repo} collaborators: {rsp.text}")

        return rsp.json()

    def get_members_with_role(self, owner):
        """Fetch current organization members with the role using GraphQL"""
        members = []
        params = {'owner': owner}
        while True:
            query = self._prepare_graphql_query(
                QUERY_MEMBERS, params
            )
            response = self.request(
                method="POST", url="graphql", json=query
            )
            errors = response.json().get("errors")
            if response.status_code >= 400 or errors:
                if not errors:
                    errors = response.text
                self.save_error(f"Error performing query: {errors}")
                break
            data = response.json()["data"]["organization"]["membersWithRole"]
            for item in data["edges"]:
                members.append({
                    "login": item["node"]["login"].lower(),
                    "role": 'Member' if item["role"] == 'MEMBER' else 'Owner'
                })
            if data["pageInfo"]["hasNextPage"]:
                # Put cursor to next page into params
                params['memberCursor'] = data["pageInfo"]["endCursor"]
            else:
                break
        return members

    def _process_member(self, owner, login, role, members, check=True):
        """Process current member - check role"""
        changed = False
        # Pop member from current members
        current_state = members.pop(login, {})
        if (current_state.get('role', '').lower() != role.lower()):
            changed = True
            if not check:
                self.update_org_membership(
                    owner, login, role)
        return (changed, role)

    def _process_invitee(self, owner, login, role, invites, check=True):
        """Process invite for single user"""
        target_invite_role = 'direct_member'
        if role.lower() == 'owner':
            target_invite_role = 'admin'
        # Pop user from invites
        invite = invites.pop(login, {})
        if invite:
            if invite['role'] != target_invite_role:
                # Invitation with wrong role - discard
                if not check:
                    self.delete_org_invitation(
                        owner, invite['id'])
            else:
                return (False, 'Already invited')

        user = self.get_user(login)
        if not check:
            self.create_organization_invitation(
                owner, user, target_invite_role)
        return (True, 'Invited')

    def _manage_org_members(self, org, target_members, exclusive=False, check=True):
        status = dict()
        changed = False
        invites_supported = True

        # Try to read current members
        try:
            current_members = {x['login'].lower(): x for x in
                               self.get_members_with_role(org)}
        except Exception:
            self.fail_json(
                msg='Cannot fetch current organization members',
                errors=self.errors)

        # Try to read current invites
        try:
            current_invites = {x['login'].lower(): x for x in
                               self.get_org_invitations(org)}
        except Exception:
            # GH Enterprise does not support invites, no worries
            invites_supported = False
            current_invites = {}

        # Loop through target users
        for member, member_props in target_members.items():
            login = member.lower()
            target_role = member_props.get('role', 'member').lower()
            msg = None
            try:
                if login not in current_members:
                    if invites_supported:
                        # Process invites
                        (is_changed, msg) = self._process_invitee(
                            org,
                            login,
                            target_role,
                            current_invites,
                            check
                        )
                    else:
                        changed = True
                        msg = target_role
                        if not self.ansible.check_mode:
                            self.update_org_membership(
                                org,
                                login,
                                target_role,
                                check
                            )
                else:
                    # Process member
                    (is_changed, msg) = self._process_member(
                        org,
                        login,
                        target_role,
                        current_members,
                        check
                    )

            except Exception as ex:
                self.save_error(f"Error processing member {login}:"
                                f"{str(ex)}")
                (is_changed, msg) = (False, str(ex))

            status[login] = msg
            if is_changed:
                changed = True

        # Cancel invitations for members not in the target state
        for login, invite in current_invites.items():
            changed = True
            if not check:
                self.delete_org_invitation(
                    org,
                    invite['id']
                )
            status[login] = 'Invite cancelled'

        # Report current members that are not in the target state
        for member, _ in current_members.items():
            if not exclusive:
                status[member] = 'Not Managed'
            else:
                if not check:
                    self.delete_org_member(
                        org,
                        member
                    )
                status[member] = 'Removed'

        return (changed, status)
