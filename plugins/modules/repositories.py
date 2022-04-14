#!/usr/bin/python

# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

DOCUMENTATION = '''
module: repositories
short_description: Manage GitHub Repository
extends_documentation_fragment: opentelekomcloud.gitcontrol.git
version_added: "0.0.1"
author: "Artem Goncharov (@gtema)"
description:
  - Manages repository options
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


class Repo(GitHubBase):
    argument_spec = dict(
        root=dict(type='str', required=False),
    )
    module_kwargs = dict(
        supports_check_mode=True
    )

    def _is_repo_update_needed(self, current, target):
        for attr in [
            'description', 'homepage', 'private', 'visibility',
            'has_issues', 'has_projects', 'has_wiki', 'is_template',
            'default_branch', 'allow_squash_merge',
            'allow_merge_commit', 'allow_rebase_merge',
            'delete_branch_on_merge', 'archived'
        ]:
            if attr in target and target[attr] != current.get(attr):
                return True

    def _is_branch_protection_update_needed(self, owner, repo, branch, target):
        current = self.get_branch_protection(owner, repo, branch)

        if not current:
            return True
        else:
            for attr in ['enforce_admins', 'required_linear_history',
                         'allow_force_pushes', 'allow_deletions',
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
            current_pr_review = current.get('required_pull_request_reviews')
            target_pr_review = target.get('required_pull_request_reviews')
            current_status_checks = current.get('required_status_checks', {})
            target_status_checks = target.get('required_status_checks', {})
            if (current_status_checks.get(
                'strict', False) != target_status_checks.get(
                    'strict', False)):
                return True

            if (
                set(
                    current_status_checks.get('contexts', [])
                ) != set(
                    target_status_checks.get('contexts', [])
                )
            ):
                return True

            if target_restrictions:
                if (
                    set(
                        [x['login'] for x in current_restrictions['users']]
                    ) != set(target_restrictions['users'])
                ):
                    return True
                if (
                    set(
                        [x['slug'] for x in current_restrictions['teams']]
                    ) != set(target_restrictions['teams'])
                ):
                    return True
                if (
                    set(
                        [x['slug'] for x in current_restrictions['apps']]
                    ) != set(target_restrictions['apps'])
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
                    c = current_pr_review['dismissal_restrictions']
                    if (
                        set(
                            [x['login'] for x in c.get('users', [])]
                        ) != set(t['users'])
                    ):
                        return True
                    if (
                        set(
                            [x['slug'] for x in c.get('teams', [])]
                        ) != set(t['teams'])
                    ):
                        return True

        return False

    def _get_privs(self, mapping):
        """Convert teams/collaborators mapping into entity/priv mapping"""
        privs = dict()
        for k, v in mapping.items():
            for priv in ['maintain', 'pull', 'push', 'admin', 'triage']:
                if isinstance(v, list):
                    for team in v:
                        if team not in privs:
                            privs[team] = dict(
                                admin=False, pull=False,
                                push=False, maintain=False, triage=False)
                        if (
                            priv in mapping
                            and isinstance(mapping[priv], list)
                            and team in mapping[priv]
                        ):
                            privs[team][priv] = True
        return privs

    def _pick_priv_from_dict(self, privs_dict):
        """Knowing hash of individual privileges return the one (first match)
        which is true.

        dict(admin=False, pull=False, push=True, maintain=False) will return
        "push"
        """
        if privs_dict.get("push") and privs_dict.get("pull"):
            return "push"
        for k, v in privs_dict.items():
            # permission setting is not getting hash, but
            # single value
            if v:
                return k

    def run(self):
        config = self.get_config()
        changed = False
        status = dict()

        for owner, val in config.items():
            status[owner] = dict()
            for repo, repo_dict in val['repositories'].items():
                status[owner][repo] = dict()
                current_repo = self.get_repo(owner, repo, ignore_missing=True)

                if not current_repo:
                    if not self.ansible.check_mode:
                        repo_args = dict(
                            description=repo_dict.get('description'),
                            homepage=repo_dict.get('homepage'),
                            private=repo_dict.get('private', False),
                            visibility=repo_dict.get('visibility', 'public'),
                            has_issues=repo_dict.get('has_issues', True),
                            has_projects=repo_dict.get('has_projects', True),
                            has_wiki=repo_dict.get('has_wiki', True),
                            # is_template=repo_dict.get('is_template', False),
                            auto_init=repo_dict.get('auto_init', False),
                            allow_squash_merge=repo_dict.get(
                                'allow_squash_merge', True),
                            allow_merge_commit=repo_dict.get(
                                'allow_merge_commit', True),
                            allow_rebase_merge=repo_dict.get(
                                'allow_rebase_merge', True),
                            allow_auto_merge=repo_dict.get(
                                'allow_auto_merge', False),
                            delete_branch_on_merge=repo_dict.get(
                                'delete_branch_on_merge', False)
                        )
                        for k in ['gitignore_template', 'license_template']:
                            if k in repo_dict:
                                repo_args[k] = repo_dict[k]
                        current_repo = self.create_repo(
                            owner, repo, **repo_args)

                if current_repo and current_repo.get('archived', False):
                    # Not doing anything on archived repos
                    continue

                if current_repo and self._is_repo_update_needed(current_repo, repo_dict):
                    changed = True
                    if not self.ansible.check_mode:
                        self.update_repo(owner, repo, **repo_dict)
                # Current state is too huge to return it
                status[owner][repo]['description'] = repo_dict

                if current_repo and 'topics' in repo_dict:
                    current_topics = self.get_repo_topics(owner, repo)
                    if set(repo_dict['topics']) != set(current_topics):
                        changed = True
                        if not self.ansible.check_mode:
                            self.update_repo_topics(
                                owner, repo, repo_dict['topics'])
                    status[owner][repo]['topics'] = repo_dict['topics']

                # TODO(gtema): collaborator management need to be done,
                # but we have not proper data structure (team, collaborator,
                # outside collaborator)
                if current_repo and 'teams' in repo_dict:
                    status[owner][repo]['teams'] = dict()
                    privs = self._get_privs(repo_dict['teams'])

                    for team in self.get_repo_teams(owner, repo):
                        # TODO: need to differentiate between org teams and
                        # project teams
                        # pop privs for the team to track which team is new
                        target_privs = privs.pop(team['slug'], {})
                        if not target_privs:
                            # Delete project access from team
                            changed = True
                            if not self.ansible.check_mode:
                                self.delete_team_repo_access(
                                    owner, team['slug'], repo)
                        target_priv = self._pick_priv_from_dict(target_privs)
                        if (
                            target_priv
                            and self._pick_priv_from_dict(
                                team['permissions']) != target_priv
                        ):
                            changed = True
                            if not self.ansible.check_mode:
                                self.update_team_repo_permissions(
                                    owner, team=team['slug'], repo=repo,
                                    priv=target_priv)

                        status[owner][repo]['teams'][team['slug']] = \
                            target_priv
                    # privs dict now contains remaining privileges
                    for team, target_privs in privs.items():
                        target_priv = self._pick_priv_from_dict(target_privs)

                        changed = True
                        if not self.ansible.check_mode:
                            self.update_team_repo_permissions(
                                owner, team=team, repo=repo,
                                priv=target_priv)
                        status[owner][repo]['teams'][team] = \
                            target_priv

                if current_repo and 'protection_rules' in repo_dict:
                    tmpl = self.get_branch_protections(
                        repo_dict['protection_rules'])

                    if (
                        self._is_branch_protection_update_needed(
                            owner, repo, repo_dict['default_branch'],
                            tmpl)
                    ):
                        changed = True
                        if not self.ansible.check_mode:
                            self.update_branch_protection(
                                owner, repo, repo_dict['default_branch'],
                                tmpl)

                    status[owner][repo]['branch_protection'] = tmpl

        if len(self.errors) == 0:
            self.exit_json(
                changed=changed,
                repositories=status,
                errors=self.errors
            )
        else:
            self.fail_json(
                msg='Failures occured',
                errors=self.errors,
                repositories=status
            )


def main():
    module = Repo()
    module()


if __name__ == "__main__":
    main()
