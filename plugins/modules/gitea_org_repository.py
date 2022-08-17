#!/usr/bin/python
#
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

DOCUMENTATION = '''
module: gitea_org_repository
short_description: Manage Gitea Organization Repository setting
extends_documentation_fragment: opentelekomcloud.gitcontrol.gitea
version_added: "0.2.0"
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
    description: a short description of the repository.
    type: str
    required: False
  allow_manual_merge:
    description: |
      either true to allow mark pr as merged manually, or false to prevent it.
      has_pull_requests must be true.
    type: bool
    required: False
  allow_merge_commits:
    description: |
      either true to allow merging pull requests with a merge commit, or false
      to prevent merging pull requests with merge commits. has_pull_requests must be true.
    type: bool
    required: False
  allow_rebase:
    description: |
      either true to allow rebase-merging pull requests, or false to prevent rebase-merging. has_pull_requests must be true.
    type: bool
    required: False
  allow_rebase_explicit:
    description: |
      either true to allow rebase with explicit merge commits (--no-ff), or false to prevent rebase with explicit merge commits. has_pull_requests must be true.
    type: bool
    required: False
  allow_rebase_update:
    description: |
      either true to allow updating pull request branch by rebase, or false to prevent it. has_pull_requests must be true.
    type: bool
    required: False
  allow_squash_merge:
    description: |
      either true to allow squash-merging pull requests, or false to prevent squash-merging. has_pull_requests must be true.
    type: bool
    required: False
  archived:
    description: |
      set to true to archive this repository.
    type: bool
    required: False
    default: False
  autodetect_manual_merge:
    description: |
      either true to enable AutodetectManualMerge, or false to prevent it. has_pull_requests must be true, Note: In some special cases, misjudgments can occur.
    type: bool
    required: False
  auto_init:
    description: |
      Whether the repository should be auto-initialized?
    type: bool
    required: False
  default_branch:
    description: |
      sets the default branch for this repository.
    type: str
    required: False
  default_delete_branch_after_merge:
    description: |
      set to true to delete pr branch after merge by default
    type: bool
    required: False
  default_merge_style:
    description: |
      set to a merge style to be used by this repository: "merge", "rebase", "rebase-merge", or "squash". has_pull_requests must be true.
    type: str
    choices: [merge, rebase, rebase-merge, squash]
    required: False
  enable_prune:
    description: |
      enable prune - remove obsolete remote-tracking references
    type: bool
    required: False
  gitignores:
    description: |
      Gitignores to use
    type: str
    required: False
  has_issues:
    description: |
      either true to enable issues for this repository or false to disable them.
    type: bool
    required: False
  has_projects:
    description: |
      either true to enable project unit, or false to disable them.
    type: bool
    required: False
  has_pull_requests:
    description: |
      either true to allow pull requests, or false to prevent pull request.
    type: bool
    required: False
  has_wiki:
    description: |
      either true to enable the wiki for this repository or false to disable it.
    type: bool
    required: False
  ignore_whitespace_conflicts:
    description: |
      either true to ignore whitespace for conflicts, or false to not ignore whitespace. has_pull_requests must be true.
    type: bool
    required: False
  issue_labels:
    description: |
      Label-Set to use
    type: str
    required: False
  license:
    description: |
      License to use
    type: str
    required: False
  private:
    description: |
      either true to make the repository private or false to make it public.
      Note: you will get a 422 error if the organization restricts changing repository visibility to organization
      owners and a non-owner tries to change the value of private.
    type: bool
    required: False
  readme:
    description: |
      Readme of the repository to create
    type: str
    required: False
  template:
    description: |
      either true to make this repository a template or false to make it a normal repository
    type: bool
    required: False
  trust_model:
    description: |
      TrustModel of the repository
    type: str
    choices: [default, collaborator, commiter, collaboratorcommiter]
    required: False
  website:
    description: |
      a URL with more information about the repository.
    type: str
    required: False
  branch_protections:
    description: Branch protection definitions.
    type: list
    elements: dict
    suboptions:
      branch_name:
        description: Branch name to protect
        type: str
        required: True
      approvals_whitelist_teams:
        description: Whitelisted teams for reviews
        type: list
        elements: str
      approvals_whitelist_username:
        description: Whitelisted usernames for reviews
        type: list
        elements: str
      block_on_official_review_requests:
        description: Merging will not be possible when it has official review requests, even if there are enough approvals.
        type: bool
      block_on_outdated_branch:
        description: Merging will not be possible when head branch is behind base branch.
        type: bool
      block_on_rejected_reviews:
        description: Merging will not be possible when changes are requested by official reviewers, even if there are enough approvals.
        type: bool
      dismiss_stale_approvals:
        description: When new commits that change the content of the pull request are pushed to the branch, old approvals will be dismissed.
        type: bool
      enable_approvals_whitelist:
        description: |
          Only reviews from whitelisted users or teams will count to the required approvals.
          Without approval whitelist, reviews from anyone with write access count to the required approvals.
        type: bool
      enable_merge_whitelist:
        description: Allow only whitelisted users or teams to merge pull requests into this branch.
        type: bool
      enable_push:
        description: Anyone with write access will be allowed to push to this branch (but not force push).
        type: bool
      enable_push_whitelist:
        description: Only whitelisted users or teams will be allowed to push to this branch (but not force push).
        type: bool
      enable_status_check:
        description: Require status checks to pass before merging.
        type: bool
      merge_whitelist_teams:
        description: Whitelisted teams for merging
        type: list
        elements: str
      merge_whitelist_usernames:
        description: Whitelisted users for merging
        type: list
        elements: str
      protected_file_patterns:
        description: Protected files that are not allowed to be changed directly even if user has rights to add, edit, or delete files in this branch.
        type: str
      unprotected_file_patterns:
        description: Unprotected files that are allowed to be changed directly if user has write access, bypassing push restriction.
        type: str
      push_whitelist_deploy_keys:
        description: Whitelist deploy keys with write access to push
        type: bool
      push_whitelist_teams:
        description: Whitelisted teams for pushing
        type: list
        elements: str
      push_whitelist_usernames:
        description: Whitelisted users for pushing
        type: list
        elements: str
      require_signed_commits:
        description: Reject pushes to this branch if they are unsigned or unverifiable.
        type: bool
      required_approvals:
        description: Allow only to merge pull request with enough positive reviews.
        type: int
      status_check_contexts:
        description: Require status checks to pass before merging.
        type: list
        elements: str
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

            * read - can pull
            * write - can pull and push, but not administer this repository.
            * administrator - can pull, push and administer this repository.

        type: str
        choices: [read, write, administrator]
        default: read
  teams:
    description: Repository collaborator teams. Permissions are managed on the team level
    type: list
    elements: str

'''


RETURN = '''
'''


EXAMPLES = '''
'''


from ansible_collections.opentelekomcloud.gitcontrol.plugins.module_utils.gitea import (
    GiteaBase
)


class GTOrgRepositoryModule(GiteaBase):
    argument_spec = dict(
        owner=dict(type='str', required=True),
        name=dict(type='str', required=True),
        state=dict(type='str', default='present',
                   choices=['present', 'absent']),
        allow_manual_merge=dict(type='bool'),
        allow_merge_commits=dict(type='bool'),
        allow_rebase=dict(type='bool'),
        allow_rebase_explicit=dict(type='bool'),
        allow_rebase_update=dict(type='bool'),
        allow_squash_merge=dict(type='bool'),
        auto_init=dict(type='bool'),
        archived=dict(type='bool', default=False),
        autodetect_manual_merge=dict(type='bool'),
        default_branch=dict(type='str'),
        default_delete_branch_after_merge=dict(type='bool'),
        default_merge_style=dict(
            type='str',
            choices=['merge', 'rebase', 'rebase-merge', 'squash']),
        description=dict(type='str', required=False),
        enable_prune=dict(type='bool'),
        gitignores=dict(type='str'),
        has_issues=dict(type='bool'),
        has_projects=dict(type='bool'),
        has_pull_requests=dict(type='bool'),
        has_wiki=dict(type='bool'),
        ignore_whitespace_conflicts=dict(type='bool'),
        issue_labels=dict(type='str'),
        license=dict(type='str'),
        private=dict(type='bool'),
        readme=dict(type='str'),
        template=dict(type='bool'),
        trust_model=dict(
            type='str',
            choices=['default', 'collaborator', 'commiter', 'collaboratorcommiter']
        ),
        website=dict(type='str'),
        branch_protections=dict(
            type='list', elements='dict', options=dict(
                approvals_whitelist_teams=dict(type='list', elements='str'),
                approvals_whitelist_username=dict(type='list', elements='str'),
                block_on_official_review_requests=dict(type='bool'),
                block_on_outdated_branch=dict(type='bool'),
                block_on_rejected_reviews=dict(type='bool'),
                branch_name=dict(type='str', required=True),
                dismiss_stale_approvals=dict(type='bool'),
                enable_approvals_whitelist=dict(type='bool'),
                enable_merge_whitelist=dict(type='bool'),
                enable_push=dict(type='bool'),
                enable_push_whitelist=dict(type='bool'),
                enable_status_check=dict(type='bool'),
                merge_whitelist_teams=dict(type='list', elements='str'),
                merge_whitelist_usernames=dict(type='list', elements='str'),
                protected_file_patterns=dict(type='str'),
                push_whitelist_deploy_keys=dict(type='bool'),
                push_whitelist_teams=dict(type='list', elements='str'),
                push_whitelist_usernames=dict(type='list', elements='str'),
                require_signed_commits=dict(type='bool'),
                required_approvals=dict(type='int'),
                status_check_contexts=dict(type='list', elements='str'),
                unprotected_file_patterns=dict(type='str')
            )
        ),
        collaborators=dict(
            type='list', elements='dict', options=dict(
                username=dict(type='str', required=True),
                permission=dict(
                    type='str', default='read',
                    choices=['administrator', 'write', 'read']
                )
            )
        ),
        teams=dict(type='list', elements='str'),
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
    module = GTOrgRepositoryModule()
    module()


if __name__ == "__main__":
    main()
