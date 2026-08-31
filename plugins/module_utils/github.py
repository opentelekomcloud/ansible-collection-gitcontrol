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
from ansible_collections.opentelekomcloud.gitcontrol.plugins.module_utils.git import (GitBase, get_links)


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

REPOSITORY_UPDATABLE_ATTRIBUTES = [
    'allow_auto_merge',
    'allow_forking',
    'allow_merge_commit',
    'allow_rebase_merge',
    'allow_squash_merge',
    'allow_update_branch',
    'archived',
    'default_branch',
    'delete_branch_on_merge',
    'description',
    'has_issues',
    'has_projects',
    'has_wiki',
    'homepage',
    'is_template',
    'private',
    'visibility'
]


def base_argument_spec(**kwargs):
    spec = dict(
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
            error_data = dict(url=url)
            for key in ['url', 'msg', 'status', 'body']:
                if key in info:
                    error_data[key] = info[key]

            error_data["response"] = response or "no response"
            error_data["response_body"] = body or "no body"
            error_data["request_url"] = url
            error_data["request_method"] = method
            if 'json' in kwargs:
                error_data["request_body"] = kwargs['json'] or 'no body'

            self.save_error(f"request failed {error_msg}: {error_data}")
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
                method='GET',
                url=url,
                headers=headers,
                timeout=timeout,
            )
            if info["status"] == 404:
                break

            url = get_links(response.headers).get("next", {}).get("url")

            yield from json.loads(content)

    def get_owner_teams(self, owner):
        """Get Team information"""
        return self.paginated_request(
            url=f'orgs/{owner}/teams',
            error_msg=f"Cannot fetch teams for {owner}"
        )

    def get_team(self, owner, name, ignore_missing=False):
        return self.request(
            url=f"orgs/{owner}/teams/{name}",
            error_msg=f"Error fetching {owner}/{name} team",
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

    def delete_team(self, owner, team_slug):
        """Delete Team"""
        return self.request(
            method='DELETE',
            url=f"orgs/{owner}/teams/{team_slug}",
            error_msg=f"Error deleting team {owner}/{team_slug}"
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
        return self.paginated_request(
            method='GET',
            url=(f"orgs/{owner}/"
                 f"teams/{team}/members?role={role}"),
            error_msg=f"Cannot fetch team {team}@{owner} with role {role}"
        )

    def get_team_repo_permissions(self, owner, team, repo):
        """Get team permissions on a repo"""
        return self.request(
            method='GET',
            url=(f"orgs/{owner}/"
                 f"teams/{team}/projects/{owner}/{repo}"),
            error_msg=f"Cannot fetch team {team}@{owner}/{repo} permissions"
        )

    def update_team_repo_permissions2(self, org, team, owner, repo, priv):
        """Set team permissions on a repo"""
        self.request(
            method='PUT',
            url=(f"orgs/{org}/"
                 f"teams/{team}/repos/{owner}/{repo}"),
            json={'permission': priv},
            error_msg=f"Cannot update team {org}:{team}@{owner}/{repo}"
                      f" permissions to {priv}"
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

    def delete_team_repo_access(self, owner, team, repo):
        """Delete repo access from team"""
        self.request(
            method='DELETE',
            url=(f"orgs/{owner}/"
                 f"teams/{team}/repos/{owner}/{repo}"),
            error_msg=f"Cannot delete team {team}@{owner}/{repo} access"
        )

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
        rsp = self.request(
            method='PUT',
            url=f'repos/{owner}/{repo}/topics',
            json={'names': topics},
            error_msg=f"Repo {repo}@{owner} topics cannot be updated"
        )

        return rsp

    def get_branch_protection(self, owner, repo, branch):
        """Get branch protection rules"""
        rsp = self.request(
            method='GET',
            url=(f'repos/{owner}/{repo}/branches/{branch}/protection'),
            error_msg=f"Repo {repo}@{owner} branch protection "
                      f"cannot be fetched"
        )

        return rsp

    def update_branch_protection(self, owner, repo, branch, target):
        """Set branch protection rules"""
        # Checks takes precedence as being more fine granular
        required_status_checks = target.get('required_status_checks', {})
        if required_status_checks:
            checks = required_status_checks.get('checks', '')
            contexts = required_status_checks.get('contexts', [])
            if checks:
                target['required_status_checks'].pop('contexts', '')
            elif contexts:
                target['required_status_checks'].pop('checks', '')
        # Restrictions is a mandatory param that supports being "null"
        restrictions = target.setdefault("restrictions", None)
        if restrictions == {}:
            target["restrictions"] = None

        self.request(
            method='PUT',
            url=(f'repos/{owner}/{repo}/branches/{branch}/protection'),
            json=target,
            error_msg=f"Repo {repo}@{owner} branch protection cannot be updated"
        )

        return True

    def get_repo_teams(self, owner, repo):
        """Get repo teams"""
        rsp = self.paginated_request(
            method='GET',
            url=(f"repos/{owner}/{repo}/teams"),
            error_msg=f"Cannot fetch team {owner}/{repo} teams"
        )

        return rsp

    def get_repo_collaborators(self, owner, repo, affiliation='direct'):
        """Get repo collaborators"""
        return self.paginated_request(
            method='GET',
            url=(f"repos/{owner}/{repo}/collaborators?affiliation={affiliation}"),
            error_msg=f"Cannot fetch repo {owner}/{repo} collaborators"
        )

    def delete_repo_collaborator(self, owner, repo, username):
        """Delete repo collaborator"""
        self.request(
            method='DELETE',
            url=(f"repos/{owner}/{repo}/collaborators/{username}"),
            error_msg=f"Cannot delete {owner}/{repo} collaborator {username}"
        )

    def update_repo_collaborator(self, owner, repo, username, permission='pull'):
        """Add/Update repo collaborator"""
        return self.request(
            method='PUT',
            url=(f"repos/{owner}/{repo}/collaborators/{username}"),
            json={
                'permission': permission
            },
            error_msg=f"Cannot add repo {owner}/{repo} collaborator"
        )

    def get_members_with_role(self, owner):
        """Fetch current organization members with the role using GraphQL"""
        members = []
        params = {'owner': owner}
        url = f"{self.gh_url}/graphql"

        while True:
            query = self._prepare_graphql_query(
                QUERY_MEMBERS, params
            )
            body, response, info = self._request(
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
            msg = f"role updated to {role.lower()}"
            if not check:
                self.update_org_membership(
                    owner, login, role)
        else:
            msg = role
        return (changed, msg)

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
        for member in target_members:
            login = member['login'].lower()
            target_role = member['role'].lower()
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
                        msg = f"invited as {target_role}"
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
        for member, ignore in current_members.items():
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
            target.get('name') != current.get('name')
        ):
            return True
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
        self, owner, slug, current, target, exclusive=False, check_mode=True
    ):
        changed = False
        status = dict()
        is_existing = True
        team_status = 'unchanged'
        if not current:

            # Create new team
            changed = True
            team_status = 'created'
            if not check_mode:
                current = self.create_team(
                    owner=owner,
                    name=slug,
                    description=target.get('description'),
                    privacy=target.get('privacy'),
                    parent=target.get('parent'),
                    maintainers=target.get('maintainer', [])
                )
                if current is None:
                    self.save_error(f"Unable to create team: {slug} / {target} with "
                                    f"maintainers : {', '.join(target.get('maintainer', []))} "
                                    "(all maintainers must be completely onboarded)")
                slug = current['slug']
            else:
                is_existing = False
        else:
            slug = current['slug']

        if not target['name']:
            target['name'] = slug
        if (
            is_existing
            and self._is_team_update_necessary(target, current)
        ):
            # Update Team
            changed = True
            team_status = 'updated'
            if not check_mode:
                self.update_team(owner, slug, **target)

        status['slug'] = slug
        status['status'] = team_status
        for attr in ['name', 'description', 'privacy']:
            status[attr] = target.get(attr)

        if is_existing:
            current_members = {
                x['login']: x for x in self.get_team_members(
                    owner, slug, role='member')
            }
            current_maintainers = {
                x['login']: x for x in self.get_team_members(
                    owner, slug, role='maintainer')
            }
        else:
            current_members = {}
            current_maintainers = {}

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
            for member, ignore in current_members.items():
                changed = True
                if not check_mode:
                    self.delete_team_member(
                        owner, slug, member)
                status['members'][member] = 'removed'
            for member, ignore in current_maintainers.items():
                changed = True
                if not check_mode:
                    self.delete_team_member(
                        owner, slug, member)
                status['maintainers'][member] = 'removed'
        return (changed, status)

    def _manage_org_teams(self, owner, teams, exclusive=False, check_mode=True):
        # Get current org teams
        status = dict()
        changed = False
        current_teams = list(self.get_owner_teams(owner))
        required_team_slugs = []
        if current_teams is None:
            self.fail_json(
                msg=f'Cannot fetch current teams for {owner}',
                errors=self.errors)

        # Go over teams required to exist
        for team in teams:
            slug = team.get('slug')
            required_team_slugs.append(slug)
            current = None
            # Find current team
            for t in current_teams:
                if t['slug'].lower() == slug.lower():
                    current = t
                    break

            (is_changed, status[slug]) = self._manage_org_team(
                owner,
                slug,
                current,
                team,
                exclusive,
                check_mode
            )
            if is_changed:
                changed = True
        if exclusive:
            for team in current_teams:
                slug = team['slug']
                if slug not in required_team_slugs:
                    changed = True
                    status[slug] = {'status': 'deleted'}
                    if not check_mode:
                        self.delete_team(
                            owner,
                            slug
                        )

        return (changed, status)

    def _is_repo_update_needed(self, current, target):
        for attr in REPOSITORY_UPDATABLE_ATTRIBUTES:
            if attr in target and target[attr] != current.get(attr):
                return True

    def _is_branch_protection_update_needed(
        self, owner, repo, branch, target, current=None
    ):
        if not current:
            current = self.get_branch_protection(owner, repo, branch)

        if not current:
            return True
        else:
            for attr in ['allow_deletions', 'allow_force_pushes',
                         'allow_fork_syncing', 'enforce_admins',
                         'required_linear_history',
                         'required_conversation_resolution']:
                if (
                    attr in target
                    and (
                        attr not in current
                        or target[attr] != current[attr]['enabled']
                    )
                ):
                    return True

        current_restrictions = current.get('restrictions')
        target_restrictions = target.get('restrictions')
        current_pr_review = current.get('required_pull_request_reviews', {})
        target_pr_review = target.get('required_pull_request_reviews', {})
        current_status_checks = current.get('required_status_checks', {})
        target_status_checks = target.get('required_status_checks', {})
        if (current_status_checks.get(
            'strict', False) != target_status_checks.get(
                'strict', False)):
            return True

        # rsc.checks:
        # Only checks or contexts can be present
        current_checks = current_status_checks.get('checks', []) or []
        target_checks = target_status_checks.get('checks', []) or []
        if current_checks or target_checks:
            if (
                set(
                    [f"{x.get('context')}:{x.get('app_id')}" for x in
                     current_checks]
                ) != set(
                    [f"{x.get('context')}:{x.get('app_id')}" for x in
                     target_checks]
                )
            ):
                return True
        else:
            # checks were not present, process contexts
            current_contexts = current_status_checks.get('contexts', []) or []
            target_contexts = target_status_checks.get('contexts', []) or []
            if (
                set(
                    current_contexts
                ) != set(
                    target_contexts
                )
            ):
                return True

        # GH api supports "null" as a way to disable restrictions on the branch
        if not target_restrictions and current_restrictions or target_restrictions and not current_restrictions:
            return True
        if target_restrictions:
            for case in [
                ('users', 'login'),
                ('teams', 'slug'),
                ('apps', 'slug')
            ]:
                if not current_restrictions or case[0] not in current_restrictions:
                    return True
                if (
                    set(
                        [x[case[1]] for x in current_restrictions[case[0]]]
                    ) != set(target_restrictions[case[0]])
                ):
                    return True

        if target_pr_review:
            for attr in ['dismiss_stale_reviews',
                         'require_code_owner_reviews',
                         'required_approving_review_count']:
                if (
                    attr in target_pr_review
                    and target_pr_review[attr] != current_pr_review.get(
                        attr, False)
                ):
                    return True

            if 'dismissal_restrictions' in target_pr_review:
                t = target_pr_review['dismissal_restrictions']

                if 'dismissal_restrictions' not in current_pr_review:
                    return True

                c = current_pr_review['dismissal_restrictions']

                for case in ['users', 'teams']:
                    if (
                        set(
                            [x['login'] for x in c.get(case, [])]
                        ) != set(t[case])
                    ):
                        return True

        return False

    def _manage_repo_teams(
        self, owner, repo_name, target, check_mode=False
    ):
        """Manage repository teams"""
        changed = False
        current_teams = {x['slug']: x['permission'] for x in
                         self.get_repo_teams(owner, repo_name) or []}
        target_teams = {x['slug']: x['permission'] for x in
                        target}
        if current_teams != target_teams:
            changed = True
            # Short check showed mismatch
            for team, current_priv in current_teams.items():
                target_priv = target_teams.pop(team, '')
                if not target_priv:
                    if not check_mode:
                        self.delete_team_repo_access(
                            owner, team, repo_name)
                    continue
                if target_priv != current_priv:
                    if not check_mode:
                        self.update_team_repo_permissions2(
                            owner, team, owner, repo_name, target_priv)
            # target_teams not contain remainings
            for team, target_priv in target_teams.items():
                if not check_mode:
                    self.update_team_repo_permissions2(
                        owner, team, owner, repo_name, target_priv)

        return changed

    def _manage_repo_collaborators(
        self, owner, repo_name, target, check_mode=False
    ):
        """Manage repository collaborators"""
        changed = False
        current_collaborators = {x['login']: x['permissions'] for x in
                                 self.get_repo_collaborators(
                                     owner, repo_name) or []}
        target_collaborators = {x['username']: x['permission'] for x in
                                target}
        if target_collaborators != current_collaborators:
            changed = True
            # Short comparison showed mismatch
            for username, permissions in current_collaborators.items():
                priv = 'pull'
                if 'push' in permissions and permissions['push']:
                    priv = 'push'
                else:
                    for p in ['pull', 'triage', 'maintain', 'admin']:
                        if permissions[p]:
                            priv = p
                            break
                target_priv = target_collaborators.pop('username', None)
                if not target_priv:
                    # Collaborator should be removed
                    if not check_mode:
                        self.delete_repo_collaborator(
                            owner, repo_name, username)
                    continue
                if target_priv != priv:
                    # Update priv
                    if not check_mode:
                        # Update as such is not really working, thus drop and
                        # create new
                        self.delete_repo_collaborator(
                            owner, repo_name, username)
                        self.update_repo_collaborator(
                            owner, repo_name, username, target_priv)
            # target now contains remainings
            for username, priv in target_collaborators.items():
                if not check_mode:
                    self.update_repo_collaborator(
                        owner, repo_name, username, priv)
        return changed

    def _manage_repository(self, state, current=None, check_mode=False, **kwargs):

        changed = False
        owner = kwargs.pop('owner')
        repo_name = kwargs.pop('name')
        current_repo = current if current else self.get_repo(owner, repo_name, ignore_missing=True)

        # When specifying a default branch on a repository which is still empty, the execution
        # fails with the following error message:
        # 'Cannot update default branch for an empty repository. Please init the repository and push first'
        # Therefore we remove this option in that case.
        if current_repo['size'] == 0:
            del kwargs['default_branch']
            self.ansible.warn(f"Repo {repo_name} does not yet have any branches or commits, cannot set the default branch")

        if not current_repo:
            changed = True
            if not check_mode:
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

        # Repo topics
        # TODO(gtema): get rid of this as soon as this becomes part of native
        # repository API
        if current_repo and 'topics' in kwargs:
            current_topics = current_repo['topics']
            if set(kwargs['topics']) != set(current_topics):
                changed = True
                if not check_mode:
                    self.update_repo_topics(
                        owner, repo_name, kwargs['topics'])
                    current_repo['topics'] = kwargs['topics']

        # Branch protections
        branch_protections = kwargs.pop('branch_protections', [])
        if current_repo and branch_protections is not None:
            current_repo['branch_protections'] = []
            for bp in branch_protections:
                if (
                    self._is_branch_protection_update_needed(
                        owner, repo_name, bp['branch'], bp)
                ):
                    changed = True
                    if not check_mode:
                        self.update_branch_protection(
                            owner, repo_name, bp['branch'], bp)
                current_repo['branch_protections'].append(bp)

        # Teams
        target_teams = kwargs.get('teams')
        if (
            current_repo and target_teams is not None
        ):
            changed = self._manage_repo_teams(
                owner, repo_name, target_teams, check_mode)

        # Collaborators
        target_collaborators = kwargs.get('collaborators')
        if (
            current_repo and target_collaborators is not None
        ):
            changed = self._manage_repo_collaborators(
                owner, repo_name, target_collaborators, check_mode)

        # If we need to archive - do this after updating everything else
        if (
            current_repo
            and archive and not current_repo.get('archived')
        ):
            changed = True
            if not check_mode:
                current_repo = self.update_repo(
                    owner, repo_name, archived=True)

        if current_repo:
            # Get rid of all those XXX_url properties
            for k in list(current_repo.keys()):
                if k.endswith('_url'):
                    current_repo.pop(k)
            org = current_repo.pop('organization', None)
            current_repo['organization'] = dict(
                login=org.get('login')
            )
            owner = current_repo.pop('owner', None)
            if owner:
                current_repo['owner'] = dict(
                    login=owner.get('login')
                )

        return (changed, current_repo)
