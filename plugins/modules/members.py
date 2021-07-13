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


from ansible_collections.opentelekomcloud.gitcontrol.plugins.module_utils.git import GitBase


class MembersModule(GitBase):
    argument_spec = dict(
        token=dict(type='str', required=True, no_log=True)
    )
    module_kwargs = dict(
        supports_check_mode=True
    )

    def run(self):
        status = dict()
        changed = False

        for owner, owner_dict in self.get_members().items():
            status[owner] = dict()

            members = self.get_org_members(owner)
            if members is None:
                self.fail_json(
                    msg='Cannot proceed without members information',
                    errors=self.errors
                )
            current_members = [x['login'] for x in members]
            current_invites = self.get_org_invitations(owner)

            for member in owner_dict['present'].get('users', []):
                login = member['login']
                if login not in current_members:
                    if login in [x['login'] for x in current_invites]:
                        status[owner][login] = 'Already invited'
                        continue
                    user = self.get_user(login)
                    changed = True
                    if not self.ansible.check_mode:
                        res = self.create_user_invitation(owner, user)
                    else:
                        res = True
                    if res:
                        status[owner][login] = 'Invited'
                    else:
                        status[owner][login] = 'Not Invited'
                else:
                    status[owner][login] = 'Member'

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
