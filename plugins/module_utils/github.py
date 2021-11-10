# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type


import os
import json

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

    def _request(self, method, url, headers=None, **kwargs):
        if not headers:
            headers = dict()

        headers.update({
            'Authorization': f"token {self.params['token']}",
            'Content-Type': "application/json",
        })
        if 'Accept' not in headers:
            headers['Accept'] = 'application/vnd.github.v3+json'

        if not url.startswith('http'):
            url = f"{self.gh_url}/{url}"

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
                self.save_error(f"{error_msg}: {info}")
        elif status == 404 and ignore_missing:
            return None
        if status == 204:
            return response
        elif body and status < 400:
            return json.loads(body)

    def paginated_request(self, url, headers=None, timeout=15, **kwargs):
        if not url.startswith('http'):
            url = f"{self.gh_url}/{url}"

        while url:
            content, response, info = self._request(
                url=url,
                headers=headers,
                timeout=timeout
            )

            url = response.headers.get("next", {}).get("url")
            for item in json.load(response.read()):
                yield item

    def get_owner_teams(self, owner):
        """Get Team information"""
        rsp = self.request(
            method='GET',
            url=f'orgs/{owner}/teams',
        )
        return rsp

    def get_team(self, owner, name, ignore_missing=False):
        return self.request(
            url=f"orgs/{owner}/teams/{name}",
            error_msg="Error fetching {owner}/{team} team",
            ignore_missing=ignore_missing
        )

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
            error_msg=f"Error creating {owner}/{name}"
        )
        return rsp

    def delete_team(self, owner, team):
        """Delete Team"""
        return self.request(
            method='DELETE',
            url=f"orgs/{owner}/teams/{team}",
            error_msg=f"Error deleting team {owner}/{team}"
        )

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

        return self.request(
            method='PATCH',
            url=f"orgs/{owner}/teams/{team}",
            json=body,
            error_msg=f"Cannot update team {team}@{owner}"
        )

    def get_team_members(self, owner, team, role='maintainer'):
        """Get team members"""
        return self.request(
            method='GET',
            url=(f"orgs/{owner}/"
                 f"teams/{team}/members?role={role}"),
            error_msg=f"Cannot fetch team {team}@{owner} {role}s"
        )

    def get_team_repo_permissions(self, owner, team, repo):
        """Get team permissions on a repo"""
        headers = dict(
            Accept='application/vnd.github.v3.repository+json'
        )
        return self.request(
            method='GET',
            url=(f"orgs/{owner}/"
                 f"teams/{team}/projects/{owner}/{repo}"),
            headers=headers,
            error_msg=f"Cannot fetch team {team}@{owner}/{repo} permissions"
        )

    def update_team_repo_permissions(self, owner, team, repo, priv):
        """Set team permissions on a repo"""
        self.request(
            method='PUT',
            url=(f"orgs/{owner}/"
                 f"teams/{team}/repos/{owner}/{repo}"),
            json={'permission': priv},
            error_msg=f"Cannot update team {team}@{owner}/{repo} permissions"
        )

        return True

    def delete_team_repo_access(self, owner, team, repo):
        """Delete repo access from team"""
        self.request(
            method='DELETE',
            url=(f"orgs/{owner}/"
                 f"teams/{team}/repos/{owner}/{repo}"),
            error_msg=f"Cannot delete team {team}@{owner}/{repo} access"
        )

        return True

    def set_team_member(self, owner, team, login, role='member'):
        """Add user into the team
        """
        return self.request(
            method='PUT',
            url=(f"orgs/{owner}/"
                 f"teams/{team}/memberships/{login}"),
            json={'role': role},
            error_msg=f"Membership {login}@{team} not updated"
        )

    def delete_team_member(self, owner, team, login):
        """Add user into the team
        """
        return self.request(
            method='PUT',
            url=(f"orgs/{owner}/"
                 f"teams/{team}/memberships/{login}"),
            error_msg=f"Membership {login}@{team} not deleted"
        )

    def get_org_members(self, owner):
        """Get organization members"""
        return self.paginated_request(
            url=f'orgs/{owner}/members',
            error_msg="Cannot fetch organizaition members"
        )

    def update_org_membership(self, owner, username, role):
        """Set organization membership for the user"""
        return self.request(
            method="PUT",
            url=f"orgs/{owner}/memberships/{username}",
            json={"role": role},
            error_msg=f"Membership for user {username} not updated"
        )

    def delete_org_membership(self, owner, username):
        """Delete organization membership for the user"""
        return self.request(
            method="DELETE",
            url=f"orgs/{owner}/memberships/{username}",
            error_msg=f"Membership for user {username} not deleted"
        )

    def get_org_invitations(self, owner):
        """List existing user invitations
        """
        return self.paginated_request(
            url=f"orgs/{owner}/invitations",
            error_msg=f"Cannot fetch invitations for {owner}"
        )

    def create_organization_invitation(self, owner, user, role='direct_member'):
        """Send Invitation to join the org"""
        return self.request(
            method='POST',
            url=f"orgs/{owner}/invitations",
            json={'invitee_id': user['id'], 'role': role},
            error_msg=f"Member {user['id']} not invited"
        )

    def delete_org_invitation(self, owner, id):
        """Cancel organization invitation"""
        return self.request(
            method='DELETE',
            url=f"orgs/{owner}/invitations/{id}",
            error_msg=f"Organization invite {owner}/{id} not cacnelled"
        )

    def delete_org_member(self, owner, login):
        """Remove organization member"""
        return self.request(
            method='DELETE',
            url=f"orgs/{owner}/members/{login}",
            error_msg=f"Organization member {owner}/{login} not removed"
        )

    def get_user(self, login):
        """Get user info"""
        user = None
        if login not in self._users_cache:
            user = self.request(
                method='GET',
                url=f"users/{login}",
            )
            if user:
                self._users_cache[login] = user
        user = self._users_cache.get(login)
        return user

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
        rsp = self.request(
            method='PATCH',
            url=f'repos/{owner}/{repo}',
            json=kwargs,
            error_msg=f"Repo {repo}@{owner} cannot be updated"
        )
        return rsp

    def get_repo_topics(self, owner, repo):
        """Get repository topics"""
        headers = dict(
            Accept='application/vnd.github.mercy-preview+json'
        )

        rsp = self.request(
            method='GET',
            url=f'repos/{owner}/{repo}/topics',
            headers=headers,
            error_msg=f"Repo {repo}@{owner} topics cannot be updated"
        )
        return rsp['names']

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
            error_msg=f"Repo {repo}@{owner} topics cannot be updated"
        )

        return rsp

    def get_branch_protection(self, owner, repo, branch):
        """Get branch protection rules"""
        headers = dict(
            Accept='application/vnd.github.luke-cage-preview+json',
        )

        rsp = self.request(
            method='GET',
            url=(f'repos/{owner}/{repo}/branches/{branch}/protection'),
            headers=headers,
            error_msg=f"Repo {repo}@{owner} branch protection "
                      f"cannot be fetched"
        )

        return rsp

    def update_branch_protection(self, owner, repo, branch, target):
        """Set branch protection rules"""
        headers = dict(
            Accept='application/vnd.github.luke-cage-preview+json',
        )

        self.request(
            method='PUT',
            url=(f'repos/{owner}/{repo}/branches/{branch}/protection'),
            headers=headers,
            json=target,
            error_msg=f"Repo {repo}@{owner} branch protection cannot be updated"
        )

        return True

    def get_repo_teams(self, owner, repo):
        """Get repo teams"""
        headers = dict(
            Accept='application/vnd.github.v3+json'
        )
        rsp = self.request(
            method='GET',
            url=(f"repos/{owner}/{repo}/teams"),
            headers=headers,
            error_msg=f"Cannot fetch team {owner}/{repo} teams"
        )

        return rsp

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
            headers=headers,
            error_msg=f"Cannot fetch team {owner}/{repo} collaborators"
        )

        return rsp

    def get_members_with_role(self, owner):
        """Fetch current organization members with the role using GraphQL"""
        members = []
        params = {'owner': owner}
        url = f"{self.gh_url}/graphql"

        while True:
            query = self._prepare_graphql_query(
                QUERY_MEMBERS, params
            )
            (body, response, info) = self._request(
                method="POST", url=url,
                data=self.ansible.jsonify(query)
            )
            status = info['status']
            data = json.loads(body)
            errors = data.get("errors")
            if status >= 400 or errors:
                if not errors:
                    errors = response.text
                self.save_error(f"Error performing query: {errors}")
                break
            data = data["data"]["organization"]["membersWithRole"]
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
        except Exception as ex:
            self.fail_json(
                msg='Cannot fetch current organization members',
                errors=self.errors,
                ex=str(ex))

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
                        is_changed = True
                        msg = target_role
                        if not check:
                            self.update_org_membership(
                                org,
                                login,
                                target_role,
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

    def _is_team_update_necessary(self, target, current):
        if (
            target.get('description') != current.get('description')
        ):
            return True
        if (
            target.get('privacy') != current.get('privacy')
        ):
            return True
        return False

    def _manage_org_team(
        self, owner, name, current, target, exclusive=False, check_mode=True
    ):
        changed = False
        slug = None
        status = dict()
        current_team = dict()
        if not current:
            # Create new team
            if not check_mode:
                current = self.create_team(
                    owner=owner,
                    name=name,
                    description=target.get('description'),
                    privacy=target.get('privacy'),
                    parent=target.get('parent'),
                    maintainers=target.get('maintainer', [])
                )
                slug = current_team['slug']
        else:
            slug = current['slug']

        if (
            slug
            and self._is_team_update_necessary(target, current)
        ):
            # Update Team
            changed = True
            if not check_mode:
                current_team = self.update_team(owner, slug, **target)

        status['name'] = current.get('slug', name)
        for attr in ['description', 'privacy']:
            status[attr] = current.get(attr)

        if slug:
            current_members = [
                {x['login']: x} for x in self.get_team_members(
                    owner, slug, role='member')
            ]
            current_maintainers = [
                {x['login']: x} for x in self.get_team_members(
                    owner, slug, role='maintainer')
            ]
        else:
            current_members = []
            current_maintainers = []

        status['members'] = dict()
        target_members = target.get('members', []) or []
        if 'member' in target:
            target_members = target.get('member', [])
        for login in target_members:
            # Member should exist
            if login not in current_members:
                changed = True
                if not check_mode:
                    self.set_team_member(
                        owner, slug, login, role='member')
                status['members'][login] = 'Added'
            else:
                status['members'][login] = 'Present'
                current_members.pop(login, None)

        status['maintainers'] = dict()
        target_maintainers = target.get('maintainers', []) or []
        if 'maintainer' in target:
            target_maintainers = target.get('maintainer', [])
        for login in target_maintainers:
            # Maintainer should exist
            if login not in current_maintainers:
                changed = True
                if not check_mode:
                    self.set_team_member(
                        owner, slug, login, role='maintainer')
                status['maintainers'][login] = 'Added'
            else:
                status['maintainers'][login] = 'Present'
                current_maintainers.pop(login, None)
        # In the exclusive mode drop maintainers and members not present in the
        # target state
        if exclusive:
            for member in current_members + current_maintainers:
                changed = True
                if not check_mode:
                    self.delete_team_member(
                        owner, slug, member)
        return (changed, status)

    def _manage_org_teams(self, owner, teams, check_mode):
        # Get current org teams
        status = dict()
        changed = False
        current_teams = self.get_owner_teams(owner)
        if current_teams is None:
            self.fail_json(
                msg=f'Cannot fetch current teams for {owner}',
                errors=self.errors)

        # Go over teams required to exist
        for team, team_dict in teams.items():
            current_team = None
            team_slug = None
            if team not in [x['slug'] for x in current_teams]:
                changed = True
                # Create new team
                if check_mode:
                    current_team = team
                else:
                    current_team = self.create_team(
                        owner=owner,
                        name=team,
                        description=team_dict.get('description'),
                        privacy=team_dict.get('privacy'),
                        parent=team_dict.get('parent'),
                        maintainers=team_dict.get('maintainer', [])
                    )
                    team_slug = current_team['slug']
            else:
                for t in current_teams:
                    if t['name'] == team:
                        current_team = t
                        team_slug = t['slug']
                        break
                if not current_team:
                    # Not able to cope with wanted team, try others
                    continue

            status[team] = dict()
            status[team]['description'] = current_team

            if (
                team_slug
                and self._is_team_update_necessary(team_dict, current_team)
            ):
                # Update Team
                changed = True
                if not check_mode:
                    self.update_team(owner, team_slug, **team_dict)
                status[team]['status'] = 'updated'

            if team_slug:
                current_members = [
                    x['login'] for x in self.get_team_members(
                        owner, team_slug, role='member')
                ]
            else:
                current_members = []

            if team_slug:
                current_maintainers = [
                    x['login'] for x in self.get_team_members(
                        owner, team_slug, role='maintainer')
                ]
            else:
                current_maintainers = []

            status[team]['members'] = dict()
            target_members = team_dict.get('member', []) or []
            for login in target_members:
                # Member should exist
                if login not in current_members:
                    changed = True
                    if not check_mode:
                        self.set_team_member(
                            owner, team_slug, login, role='member')
                    status[team]['members'][login] = 'Added'
                else:
                    status[team]['members'][login] = 'Present'

            status[team]['maintainers'] = dict()
            target_maintainers = team_dict.get('maintainer', []) or []
            for login in target_maintainers:
                # Maintainer should exist
                if login not in current_maintainers:
                    changed = True
                    if not check_mode:
                        self.set_team_member(
                            owner, team_slug, login, role='maintainer')
                    status[team]['maintainers'][login] = 'Added'
                else:
                    status[team]['maintainers'][login] = 'Present'
        return (changed, status)
