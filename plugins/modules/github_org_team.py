#!/usr/bin/python
#
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type


DOCUMENTATION = '''
module: github_org_team
short_description: Manage GitHub Organization Team
extends_documentation_fragment: opentelekomcloud.gitcontrol.github
version_added: "0.0.2"
author: "Artem Goncharov (@gtema)"
description:
  - Manages organization teams.
options:
  organization:
    description: Name of the GitHub organization
    type: str
    required: True
  state:
    description: Team state
    type: str
    choices: [present, absent]
    default: present
  slug:
    description: Team slug.
    type: str
    required: true
  name:
    description: Team name.
    type: str
    required: False
  description:
    description: Team description
    type: str
    required: False
  privacy:
    description: |
      The level of privacy this team should have. The options are:
      For a non-nested team:
      * secret - only visible to organization owners and members of this team.
      * closed - visible to all members of this organization.
      Default: secret
      For a parent or child team:
      * closed - visible to all members of this organization.
      Default for child team: closed
    type: str
    choices: [secret, closed]
    default: secret
    required: False
  maintainers:
    description: List GitHub IDs for organization members who will become team maintainers.
    type: list
    elements: str
    required: False
    default: []
  members:
    description: List GitHub IDs for organization members who will become team
    members.
    type: list
    elements: str
    required: False
    default: []
  exclusive:
    description: Whether only listed members and maintainers should be present.
    type: bool
    default: false
'''


RETURN = '''
opentelekomcloud.gitcontrol.github_org_team:
  description: List of organization teams statuses
  returned: always
  type: list
  elements: str
'''


EXAMPLES = '''
- name: Apply org members
  opentelekomcloud.gitcontrol.github_org_team:
    token: "{{ secret }}"
    organization: "test_org"
    description: description of the team
    maintainers:
      - userA
    members:
      - userB
'''


from ansible_collections.opentelekomcloud.gitcontrol.plugins.module_utils.github import GitHubBase


class GHOrgTeamModule(GitHubBase):
    argument_spec = dict(
        organization=dict(type='str', required=True),
        state=dict(type='str', choices=['present', 'absent'],
                   default='present'),
        slug=dict(type='str', required=True),
        name=dict(type='str', required=False),
        description=dict(type='str', required=False),
        privacy=dict(
            type='str', required=False, choices=['secret', 'closed'],
            default='secret'),
        maintainers=dict(type='list', elements='str', default=[]),
        members=dict(type='list', elements='str', default=[]),
        exclusive=dict(type='bool', default=False),
    )
    module_kwargs = dict(
        supports_check_mode=True
    )

    def run(self):
        changed = False
        owner = self.params['organization']
        slug = self.params['slug']
        status = None

        current_team = self.get_team(owner, slug, ignore_missing=True)
        if self.params['state'] == 'absent' and current_team:
            changed = True
            if not self.ansible.check_mode:
                self.delete_team(owner, slug)
        else:
            changed, status = self._manage_org_team(
                owner,
                slug,
                current_team,
                {
                    'name': self.params['name'],
                    'description': self.params['description'],
                    'privacy': self.params['privacy'],
                    'maintainers': self.params['maintainers'],
                    'members': self.params['members']
                },
                exclusive=self.params['exclusive'],
                check_mode=self.ansible.check_mode
            )

        if len(self.errors) == 0:
            self.exit_json(
                changed=changed,
                team=status
            )
        else:
            self.fail_json(
                msg='Failures occured',
                errors=self.errors,
            )


def main():
    module = GHOrgTeamModule()
    module()


if __name__ == "__main__":
    main()
