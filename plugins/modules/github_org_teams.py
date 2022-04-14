#!/usr/bin/python
#
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type


DOCUMENTATION = '''
module: github_org_teams
short_description: Manage GitHub Organization Teams
extends_documentation_fragment: opentelekomcloud.gitcontrol.github
version_added: "0.0.2"
author: "Artem Goncharov (@gtema)"
description:
  - Manages organization teams.
options:
  root:
    description: Checkout directory
    type: str
    required: False
  organization:
    description: Name of the GitHub organization
    type: str
    required: True
  teams:
    description: Dictionary of organization teams
    type: list
    required: True
    elements: dict
    suboptions:
      slug:
        description: Team slug
        type: str
        required: True
      name:
        description: Team name
        type: str
        required: False
      description:
        description: Team description
        type: str
        required: False
      privacy:
        description: Team privacy option
        type: str
        choices: [secret, closed]
        default: secret
      parent:
        description: Slug of the parent team
        type: str
        required: False
      maintainers:
        description: List of team maintainers
        type: list
        elements: str
        required: False
        aliases: [maintainer]
      members:
        description: List of team members
        type: list
        elements: str
        required: False
        aliases: [member]
  exclusive:
    description: |
      Whether exclusive mode should be enabled. This enforces that not
      configured, but existing teams as well as team maintainers and members
      will be deleted.
    type: bool
    default: False
'''


RETURN = '''
opentelekomcloud.gitcontrol.github_org_teams:
  description: List of organization teams statuses
  returned: always
  type: list
  elements: str
'''


EXAMPLES = '''
- name: Apply org members
  opentelekomcloud.gitcontrol.github_org_teams:
    token: "{{ secret }}"
    organization: "test_org"
    teams:
      team1:
        description: description of the team
        maintainer:
            - userA
        member:
            - userB
'''


from ansible_collections.opentelekomcloud.gitcontrol.plugins.module_utils.github import GitHubBase


class GHOrgTeamsModule(GitHubBase):
    argument_spec = dict(
        organization=dict(type='str', required=True),
        teams=dict(
            type='list',
            required=True,
            elements='dict',
            options=dict(
                slug=dict(type='str', required=True),
                name=dict(type='str', required=False),
                description=dict(type='str', required=False),
                privacy=dict(type='str', choices=['secret', 'closed'],
                             default='secret'),
                parent=dict(type='str', required=False),
                maintainers=dict(
                    type='list',
                    elements='str',
                    aliases=['maintainer']
                ),
                members=dict(
                    type='list',
                    elements='str',
                    aliases=['member']
                )
            )
        ),
        exclusive=dict(type='bool', default=False),
    )
    module_kwargs = dict(
        supports_check_mode=True
    )

    def run(self):
        status = dict()
        changed = False

        (changed, status) = self._manage_org_teams(
            self.params['organization'],
            self.params['teams'],
            self.params['exclusive'],
            self.ansible.check_mode
        )

        if len(self.errors) == 0:
            self.exit_json(
                changed=changed,
                teams=status
            )
        else:
            self.fail_json(
                msg='Failures occured',
                errors=self.errors,
                teams=status
            )


def main():
    module = GHOrgTeamsModule()
    module()


if __name__ == "__main__":
    main()
