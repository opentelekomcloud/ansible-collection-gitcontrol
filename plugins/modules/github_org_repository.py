#!/usr/bin/python
#
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

DOCUMENTATION = '''
module: github_org_repository
short_description: Manage GitHub Organization Repository setting
extends_documentation_fragment: opentelekomcloud.gitcontrol.github
version_added: "0.0.2"
author: "Artem Goncharov (@gtema)"
description:
  - Manages organization repositories inside of the organization repository
options:
  owner:
    description: Name of the GitHub organization
    type: str
    required: True
  name:
    description: Repository name
    type: str
    required: True
  state:
    description: Repository state
    type: str
    choices: [present, absent]
    default: present
  description:
    description: Repository description
    type: str
    required: False
  homepage:
    description: Repository homepage link
    type: str
    required: False
  private:
    description: Whether the repository is private.
    type: bool
    default: False
  visibility:
    description: |
      Can be public or private. If your organization is associated with an
      enterprise account using GitHub Enterprise Cloud or GitHub Enterprise
      Server 2.20+, visibility can also be internal.
    type: str
    choices: [public, private, internal]
    default: public
  has_issues:
    description: Either true to enable issues for this repository or false to disable them.
    type: bool
    default: True
  has_projects:
    description: |
      Either true to enable projects for this repository or false to disable
      them. Note: If you're creating a repository in an organization that has
      disabled repository projects, the default is false, and if you pass true,
      the API returns an error.
    type: bool
    default: True
  has_wiki:
    description: |
      Either true to enable the wiki for this repository or false to disable it.
    type: bool
    default: True
  is_template:
    description: |
      Either true to make this repo available as a template repository or false
      to prevent it.
    type: bool
    default: False
  auto_init:
    description: |
      Pass true to create an initial commit with empty README.
    type: bool
    default: False
  gitignore_template:
    description: |
      Desired language or platform .gitignore template to apply. Use the name
      of the template without the extension. For example, "Haskell".
    type: str
    required: False
  license_template:
    description: |
      Choose an open source license template that best suits your needs, and
      then use the license keyword as the license_template string. For example,
      "mit" or "mpl-2.0".
    type: str
  allow_squash_merge:
    description: |
      Either true to allow squash-merging pull requests, or false to prevent
      squash-merging.
    type: bool
    default: True
  allow_forking:
    description: |
      Either true to allow private forks, or false to prevent private forks.
      Please note that setting this attribute requires organization to overall
      allow forking of private repositories, otherwise GitHub refuses setting
      this variable to any value.
    type: bool
  allow_merge_commit:
    description: |
      Either true to allow merging pull requests with a merge commit, or false
      to prevent merging pull requests with merge commits.
    type: bool
    default: True
  allow_rebase_merge:
    description: |
      Either true to allow rebase-merging pull requests, or false to prevent
      rebase-merging.
    type: bool
    default: True
  allow_auto_merge:
    description: |
      Either true to allow auto-merge on pull requests, or false to disallow
      auto-merge.
    type: bool
    default: False
  allow_update_branch:
    description: |
      Either true to always allow a pull request head branch that is behind its
      base branch to be updated even if it is not required to be up to date
      before merging, or false otherwise. Default: false
    type: bool
    default: False
  delete_branch_on_merge:
    description: |
      Either true to allow automatically deleting head branches when pull
      requests are merged, or false to prevent automatic deletion.
    type: bool
    default: False
  default_branch:
    description: |
      Default branch name for the repository.
    type: str
  archived:
    description: |
      true to archive this repository. Note: You cannot unarchive repositories
      through the API.
    type: bool
    default: False
  topics:
    description: |
      An array of topics to add to the repository.
    type: list
    elements: str
    default: []
  teams:
    description: |
      Repository teams with their permissions
    type: list
    elements: dict
    suboptions:
      slug:
        description: Team slug
        type: str
        required: True
      permission:
        description: |
          The permission to grant to the team for this project. Can be one of:

            * pull - can pull, but not push to or administer this repository.
            * push - can pull and push, but not administer this repository.
            * admin - can pull, push and administer this repository.
            * maintain - Recommended for project managers who need to manage the repository without access to sensitive or destructive actions.
            * triage - Recommended for contributors who need to proactively manage issues and pull requests without write access.
        type: str
        choices: [pull, push, admin, maintain, triage]
        default: pull
  collaborators:
    description: |
      Repository collaborators with their permissions
    type: list
    elements: dict
    suboptions:
      username:
        description: Username
        type: str
        required: True
      permission:
        description: |
          The permission to grant the collaborator. Only valid on
          organization-owned repositories. Can be one of:

            * pull - can pull, but not push to or administer this repository.
            * push - can pull and push, but not administer this repository.
            * admin - can pull, push and administer this repository.
            * maintain - Recommended for project managers who need to manage the repository without access to sensitive or destructive actions.
            * triage - Recommended for contributors who need to proactively manage issues and pull requests without write access.

        type: str
        choices: [pull, push, admin, maintain, triage]
        default: pull
  branch_protections:
    description: |
      Branch protection definitions.
    type: list
    elements: dict
    suboptions:
      branch:
        description: Branch name to protect.
        type: str
        required: True
      required_status_checks:
        description: Require status checks to pass before merging.
        type: dict
        required: True
        suboptions:
          strict:
            description: Require branches to be up to date before merging.
            type: bool
            default: False
          contexts:
            description: |
              The list of status checks to require in order to merge into this
              branch. If any of these checks have recently been set by a
              particular GitHub App, they will be required to come from that
              app in future for the branch to merge. Use checks instead of
              contexts for more fine-grained control.
            type: list
            elements: str
            default: []
          checks:
            description: |
              The list of status checks to require in order to merge into this
              branch.
            type: list
            elements: dict
            suboptions:
              context:
                description: |
                  The name of the required check.
                type: str
              app_id:
                description: |
                  The ID of the GitHub App that must provide this check. Set to
                  null to accept the check from any source.
                type: int
      enforce_admins:
        description: |
          Enforce all configured restrictions for administrators. Set
          to true to enforce required status checks for repository
          administrators.
        type: bool
        default: False
      required_pull_request_reviews:
        description: |
          Require at least one approving review on a pull request,
          before merging.
        type: dict
        suboptions:
          dismissal_restrictions:
            description: |
              Specify which users and teams can dismiss pull request reviews.
            type: dict
            suboptions:
              users:
                description: |
                  The list of user logins with dismissal access.
                type: list
                elements: str
                default: []
              teams:
                description: |
                  The list of team slugs with dismissal access.
                type: list
                elements: str
                default: []
          dismiss_stale_reviews:
            description: |
              Set to true if you want to automatically dismiss approving
              reviews when someone pushes a new commit.
            type: bool
            default: True
          require_code_owner_reviews:
            description: |
              Blocks merging pull requests until code owners review them.
            type: bool
            default: True
          required_approving_review_count:
            description: |
              Specify the number of reviewers required to approve pull
              requests. Use a number between 1 and 6.
            type: int
            choices: [1, 2, 3, 4, 5]
      restrictions:
        description: |
          Restrict who can push to the protected branch. User, app,
          and team restrictions are only available for organization-owned repositories.
        type: dict
        suboptions:
          allow_org_members:
            description: |
              Set to true if you want to allow all org to have push access.
              (in that case all other restrictions are ignored)
            type: bool
            default: False
          users:
            description: |
              The list of user logins with push access.
            type: list
            elements: str
            default: []
          teams:
            description: |
              The list of team slugs with push access.
            type: list
            elements: str
            default: []
          apps:
            description: |
              The list of app slugs with push access.
            type: list
            elements: str
            default: []
      required_linear_history:
        description: |
          Enforces a linear commit Git history, which prevents anyone from
          pushing merge commits to a branch. Set to true to enforce a linear
          commit history.
        type: bool
        default: False
      allow_fork_syncing:
        description: |
          Whether users can pull changes from upstream when the branch is
          locked. Set to true to allow fork syncing. Set to false to prevent
          fork syncing. Default: false
        type: bool
        default: false
      allow_force_pushes:
        description: |
          Permits force pushes to the protected branch by anyone with write
          access to the repository. Set to true to allow force pushes.
        type: bool
        default: False
      allow_deletions:
        description: |
          Allows deletion of the protected branch by anyone with write access
          to the repository.
        type: bool
        default: False
      required_conversation_resolution:
        description: |
          Requires all conversations on code to be resolved before a pull
          request can be merged into a branch that matches this rule.
        type: bool
        default: False
'''


RETURN = '''
'''


EXAMPLES = '''
'''


from ansible_collections.opentelekomcloud.gitcontrol.plugins.module_utils.github import (
    GitHubBase
)


class GHOrgRepositoryModule(GitHubBase):
    argument_spec = dict(
        owner=dict(type='str', required=True),
        name=dict(type='str', required=True),
        state=dict(type='str', default='present',
                   choices=['present', 'absent']),
        description=dict(type='str', required=False),
        homepage=dict(type='str', required=False),
        private=dict(type='bool', default=False),
        visibility=dict(type='str', default='public',
                        choices=['public', 'private', 'internal']),
        has_issues=dict(type='bool', default=True),
        has_projects=dict(type='bool', default=True),
        has_wiki=dict(type='bool', default=True),
        is_template=dict(type='bool', default=False),
        auto_init=dict(type='bool', default=False),
        gitignore_template=dict(type='str'),
        license_template=dict(type='str'),
        allow_forking=dict(type='bool'),
        allow_squash_merge=dict(type='bool', default=True),
        allow_merge_commit=dict(type='bool', default=True),
        allow_rebase_merge=dict(type='bool', default=True),
        allow_auto_merge=dict(type='bool', default=False),
        allow_update_branch=dict(type='bool', default=False),
        delete_branch_on_merge=dict(type='bool', default=False),
        default_branch=dict(type='str'),
        archived=dict(type='bool', default=False),
        topics=dict(type='list', elements='str', default=[]),
        branch_protections=dict(
            type='list', required=False, elements='dict', options=dict(
                allow_deletions=dict(type='bool', default=False),
                allow_fork_syncing=dict(type='bool', default=False),
                allow_force_pushes=dict(type='bool', default=False),
                branch=dict(type='str', required=True),
                enforce_admins=dict(type='bool', default=False),
                required_conversation_resolution=dict(type='bool',
                                                      default=False),
                required_status_checks=dict(
                    type='dict', required=True,
                    required_one_of=[('contexts', 'checks')],
                    options=dict(
                        strict=dict(type='bool', default=False),
                        contexts=dict(type='list', elements='str', default=[]),
                        checks=dict(
                            type='list', elements='dict', options=dict(
                                context=dict(type='str'),
                                app_id=dict(type='int')
                            )
                        )
                    )
                ),
                required_linear_history=dict(type='bool', default=False),
                required_pull_request_reviews=dict(
                    type='dict', options=dict(
                        dismissal_restrictions=dict(
                            type='dict', options=dict(
                                users=dict(type='list', elements='str', default=[]),
                                teams=dict(type='list', elements='str', default=[])
                            )
                        ),
                        dismiss_stale_reviews=dict(type='bool', default=True),
                        require_code_owner_reviews=dict(
                            type='bool', default=True),
                        required_approving_review_count=dict(type='int',
                                                             choices=[
                                                                 1, 2, 3,
                                                                 4, 5])
                    )
                ),
                restrictions=dict(
                    type='dict',
                    options=dict(
                        allow_org_members=dict(type='bool', default=False),
                        users=dict(type='list', elements='str', default=[]),
                        teams=dict(type='list', elements='str', default=[]),
                        apps=dict(type='list', elements='str', default=[])
                    )
                )
            )
        ),
        teams=dict(
            type='list', elements='dict', options=dict(
                slug=dict(type='str', required=True),
                permission=dict(
                    type='str', default='pull',
                    choices=['pull', 'push', 'admin', 'maintain', 'triage']
                )
            )
        ),
        collaborators=dict(
            type='list', elements='dict', options=dict(
                username=dict(type='str', required=True),
                permission=dict(
                    type='str', default='pull',
                    choices=['pull', 'push', 'admin', 'maintain', 'triage']
                )
            )
        ),
    )
    module_kwargs = dict(
        supports_check_mode=True
    )

    def run(self):
        changed = False
        repo = dict()

        state = self.params.pop('state')
        target_attrs = self.params

        current_state = self.get_repo(
            target_attrs['owner'],
            target_attrs['name'],
            ignore_missing=True
        )

        if current_state and state == 'absent':
            changed = True
            if not self.ansible.check_mode:
                self.delete_repo(
                    target_attrs['owner'],
                    target_attrs['name']
                )
            repo = {}
        else:
            changed, repo = self._manage_repository(
                state=state,
                current=current_state,
                check_mode=self.ansible.check_mode,
                **target_attrs
            )
        if len(self.errors) == 0:
            self.exit_json(
                changed=changed,
                repository=repo
            )
        else:
            self.fail_json(
                msg='Failures occured',
                errors=self.errors,
                repository=repo
            )


def main():
    module = GHOrgRepositoryModule()
    module()


if __name__ == "__main__":
    main()
