#!/usr/bin/python
#
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

DOCUMENTATION = '''
module: members
short_description: Manage GitHub Organization Members
extends_documentation_fragment: opentelekomcloud.gitcontrol.git
version_added: "0.0.1"
author: "Artem Goncharov (@gtema)"
description:
  - Manages organization members inside of the organization repository
options:
  token:
    description: GitHub token
    type: str
    required: True
'''

RETURN = '''
'''

EXAMPLES = '''
'''

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


from ansible_collections.opentelekomcloud.gitcontrol.plugins.module_utils.git import GitBase


class MembersModule(GitBase):
    argument_spec = dict(
        token=dict(type='str', required=True, no_log=True)
    )
    module_kwargs = dict(
        supports_check_mode=True
    )

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
                    "login": item["node"]["login"],
                    "role": 'Member' if item["role"] == 'MEMBER' else 'Owner'
                })
            if data["pageInfo"]["hasNextPage"]:
                # Put cursor to next page into params
                params['memberCursor'] = data["pageInfo"]["endCursor"]
            else:
                break
        return members

    def process_member(self, owner, login, role, members):
        """Process current member - check role"""
        changed = False
        # Pop member from current members
        current_state = members.pop(login, {})
        if (current_state['role'].lower() != role.lower()):
            changed = True
            if not self.ansible.check_mode:
                self.update_org_membership(
                    owner, login, role)
        return (changed, role)

    def process_invitee(self, owner, login, role, invites):
        """Process invite for single user"""
        target_invite_role = 'direct_member'
        if role.lower() == 'owner':
            target_invite_role = 'admin'
        # Pop user from invites
        invite = invites.pop(login, {})
        if invite:
            if invite['role'] != target_invite_role:
                # Invitation with wrong role - discard
                if not self.ansible.check_mode:
                    self.delete_org_invitation(
                        self, owner, invite['id'])
            else:
                return (False, 'Already invited')

        user = self.get_user(login)
        if not self.ansible.check_mode:
            self.create_organization_invitation(
                owner, user, target_invite_role)
        return (True, 'Invited')

    def run(self):
        status = dict()
        changed = False

        for owner, owner_dict in self.get_members().items():
            status[owner] = dict()

            current_members = {x['login']: x for x in
                               self.get_members_with_role(owner)}
            if current_members is None:
                self.fail_json(
                    msg='Cannot proceed without members information',
                    errors=self.errors
                )

            current_invites = {x['login']: x for x in
                               self.get_org_invitations(owner)}

            target_users = owner_dict['present'].get('users', [])
            for member in target_users:
                msg = None
                is_changed = False
                login = member['login']
                if login not in current_members:
                    # Process invites
                    (is_changed, msg) = self.process_invitee(
                        owner, login, member['role'], current_invites
                    )
                else:
                    # Process member
                    (is_changed, msg) = self.process_member(
                        owner, login, member['role'], current_members)

                status[owner][login] = msg
                if is_changed:
                    changed = True

            # Cancel invitations for members not in the target state
            for login, invite in current_invites.items():
                changed = True
                if not self.ansible.check_mode:
                    self.delete_org_invitation(owner, invite['id'])
                status[owner][login] = 'Invite cancelled'

            # Report current members that are not in the target state
            for member, _ in current_members.items():
                status[owner][member] = 'Not Managed'

        if len(self.errors) == 0:
            self.exit_json(
                changed=changed,
                members=status
            )
        else:
            self.fail_json(
                msg='Failures occured',
                errors=self.errors,
                members=status
            )


def main():
    module = MembersModule()
    module()


if __name__ == "__main__":
    main()
