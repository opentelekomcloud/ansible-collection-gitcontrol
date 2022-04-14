#!/usr/bin/python
#
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

DOCUMENTATION = '''
module: github_org_members
short_description: Manage GitHub Organization Members
extends_documentation_fragment: opentelekomcloud.gitcontrol.github
version_added: "0.0.2"
author: "Artem Goncharov (@gtema)"
description:
  - Manages organization members inside of the organization repository
options:
  root:
    type: str
    required: False
  organization:
    description: Name of the GitHub organization
    type: str
    required: True
  members:
    description: Dictionary of organization members with permissions
    type: list
    required: True
    elements: dict
    suboptions:
      login:
        description: User login.
        type: str
        required: True
      name:
        description: Optional user name (for the reference, it is not used)
        type: str
        required: False
      role:
        description: Member role.
        type: str
        choices: [member, admin]
        default: member
  exclusive:
    description: |
      Flag specifying whether unmanaged organization members should be removed
      or not.
    type: bool
    default: False
    required: False
'''


RETURN = '''
members:
  description: List of organization member statuses
  returned: always
  type: list
  elements: str
'''


EXAMPLES = '''
- name: Apply org members
  opentelekomcloud.gitcontrol.github_org_members:
    token: "{{ secret }}"
    organization: "test_org"
    members:
      - login: github_user1
        name: "some not required user name"
        role: "member"
'''


from ansible_collections.opentelekomcloud.gitcontrol.plugins.module_utils.github import (
    GitHubBase
)


class GHOrgMembersModule(GitHubBase):
    argument_spec = dict(
        organization=dict(type='str', required=True),
        members=dict(
            type='list',
            required=True,
            elements='dict',
            options=dict(
                login=dict(type='str', required=True),
                name=dict(type='str', required=False),
                role=dict(type='str', choices=['member', 'admin'],
                          default='member', required=False),
            ),
        ),
        exclusive=dict(type='bool', default=False)
    )
    module_kwargs = dict(
        supports_check_mode=True
    )

    def run(self):
        status = dict()
        changed = False

        (changed, status) = self._manage_org_members(
            self.params['organization'],
            self.params['members'],
            self.params['exclusive'],
            self.ansible.check_mode
        )

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
    module = GHOrgMembersModule()
    module()


if __name__ == "__main__":
    main()
