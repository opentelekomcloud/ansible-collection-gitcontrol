#!/usr/bin/python
#
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

DOCUMENTATION = '''
module: members
short_description: Manage GitHub Organization Members
extends_documentation_fragment: opentelekomcloud.gitcontrol.github
version_added: "0.0.1"
author: "Artem Goncharov (@gtema)"
description:
  - Manages organization members inside of the organization repository
options:
  root:
    type: str
    required: False
  token:
    description: GitHub token
    type: str
    required: True
'''


RETURN = '''
'''


EXAMPLES = '''
'''


from ansible_collections.opentelekomcloud.gitcontrol.plugins.module_utils.github import (
    GitHubBase
)


class MembersModule(GitHubBase):
    argument_spec = dict(
        root=dict(type='str', required=False),
    )
    module_kwargs = dict(
        supports_check_mode=True
    )

    def run(self):
        status = dict()
        changed = False

        for owner, owner_dict in self.get_members().items():
            (org_changed, status[owner]) = self._manage_org_members(
                owner,
                owner_dict['present'].get('users', []),
                False,
                self.ansible.check_mode
            )
            if org_changed:
                changed = True

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
