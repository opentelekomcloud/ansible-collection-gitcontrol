#!/usr/bin/python
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

DOCUMENTATION = '''
module: teams
short_description: Manage GitHub Organization Teams
extends_documentation_fragment: opentelekomcloud.gitcontrol.git
version_added: "0.0.1"
author: "Artem Goncharov (@gtema)"
description:
  - Manages team members inside of the organization repository
options:
  root:
    description: Checkout directory
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


from ansible_collections.opentelekomcloud.gitcontrol.plugins.module_utils.github import GitHubBase


class TeamsModule(GitHubBase):
    argument_spec = dict(
        root=dict(type='str', required=False),
    )
    module_kwargs = dict(
        supports_check_mode=True
    )

    def run(self):
        status = dict()
        changed = False

        for owner, owner_dict in self.get_teams().items():
            teams = []
            for slug, team in owner_dict['present']['teams'].items():
                team['slug'] = slug
                team['name'] = slug
                teams.append(team)

            (is_changed, status[owner]) = self._manage_org_teams(
                owner,
                teams,
                self.ansible.check_mode)

        if len(self.errors) == 0:
            self.exit_json(
                changed=changed,
                teams=status,
                errors=self.errors
            )
        else:
            self.fail_json(
                msg='Failures occured',
                errors=self.errors,
                teams=status
            )


def main():
    module = TeamsModule()
    module()


if __name__ == "__main__":
    main()
