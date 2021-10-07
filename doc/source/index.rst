=============================
Ansible-collection-gitcontrol
=============================

This collection helps to automate management of the GitHub organization using Ansible.


Data Structure
--------------

Describe all your organizations in `orgs/{{ structure_name }}/`,

**Each organization must have next folder structure:**

.. code-block:: yaml

   org:
     name:
       people:
         dismissed_members.yml
         members.yml
       repositories:
         repo_name.yml
       teams:
         dismissed_members.yml
         members.yml

```Currently works only repo management```

Repositories
------------

Describe your repositories in `orgs/my_org/repositories/my_repo.yml`, file name should be equal to repo name, and one repo per file:

.. code-block:: yaml

   my_repo:
     default_branch: main
     description: >-
       Brief description.  Try to fit it in one line.  As linefeeds are not allowed here.
     homepage: https://example.com
     language: Python
     archived: true / false # this is one direction road: once archived the repo can be unarchived via web only
     has_issues: true / false
     has_projects: true
     has_wiki: true / false
     private: true / false
     delete_branch_on_merge: false
     allow_merge_commit: false
     allow_squash_merge: true
     allow_rebase_merge : false
     teams:
       maintain: # List of teams who need to manage the repository without access to sensitive or destructive actions.
       pull: # List of teams who can only read this repo.
       push: # List of teams with push access.
       admin: # List of admin teams.
         - csm
     collaborators:
       maintain: # List of members who need to manage the repository without access to sensitive or destructive actions.
       pull: # List of members who can only read this repo.
       push: # List of members with push access.
       admin:  # List of admin members.
         - anton-sidelnikov
     topics:  # List of repository topics.
       - a
       - b
       - c
     protection_rules: # do not change protection rules structure all fields is required
       main: # branch name which already created in branch protection rules
         required_status_checks:
           strict: true / false
           contexts: # The list of status checks to require in order to merge into this branch
             - eco/check
         enforce_admins: true
         required_pull_request_reviews:
           dismissal_restrictions:
             users: [] # list of members or empty list
             teams: [] # list of teams or empty list
           dismiss_stale_reviews: true
           require_code_owner_reviews: false
           required_approving_review_count: 1
         restrictions:
           users: [] # list of members or empty list
           teams: [] # list of teams or empty list
           apps: # list of app slugs with push access
             - otc-zuul
         required_linear_history: false
         allow_force_pushes: false
         allow_deletions: false


Protection rules can be setted up through templates which should exist in **/templates**

**Note:** Please note it is not possible to set up branch protection rulesfor
the repository unless branch (`default_branch`) exists. This is especially the
case for newly created repositories.

Branch Protection Templates
---------------------------

Under the `<ROOT>/templates/<TEMPLATE_NAME>.yml` a file with following content
can be placed:

.. code-block:: yaml

   my_repo:
     default_branch: main
     description: >-
       Brief description.  Try to fit it in one line.  As linefeeds are not allowed here.
     homepage: https://example.com
     language: Python
     archived: true / false # this is one direction road: once archived the repo can be unarchived via web only
     has_issues: true / false
     has_projects: true
     has_wiki: true / false
     private: true / false
     delete_branch_on_merge: false
     allow_merge_commit: false
     allow_squash_merge: true
     allow_rebase_merge : false
     teams:
       maintain: # List of teams who need to manage the repository without access to sensitive or destructive actions.
       pull: # List of teams who can only read this repo.
       push: # List of teams with push access.
       admin: # List of admin teams.
         - csm
     collaborators:
       maintain: # List of members who need to manage the repository without access to sensitive or destructive actions.
       pull: # List of members who can only read this repo.
       push: # List of members with push access.
       admin:  # List of admin members.
         - anton-sidelnikov
     topics:  # List of repository topics.
       - a
       - b
       - c
     protection_rules: template_name

* Those teams and collaborators should exist in organization.

Users
-----

Under the `ROOT/ORG_NAME/users/members.yml` a yaml file describing desired
users must be placed

.. code-block:: yaml

   users:
     - name: "User1"
       login: "usr1"
       visibility: Public
       role: Member

A second file `ROOT/ORG_NAME/users/dismissed_members.yaml` must be also placed
with currently only dummy content (removing users from organizations is not yet
supported.

.. code-block:: yaml

   dismissed_users: {}

Teams
-----

Under the `ROOT/ORG_NAME/teams/members.yml` a file describing desired teams
must be placed.

.. code-block:: yaml

   teams:
     storage:  # Team name (slug)
       description: Test team
       privacy: closed  # privacy according to https://docs.github.com/en/enterprise-server@3.0/rest/reference/teams#create-a-team
       parent:
       maintainer:
         - github_user1
       member:
         - github_user2

A second file `ROOT/ORG_NAME/teams/dismissed_members.yaml` must be also placed
with currently only dummy content (removing teams from organizations is not yet
supported.

.. code-block:: yaml

   dissmissed_in_teams: {}

How to use it
-------------

As a prerequisite, a `PAT <https://docs.github.com/en/github/authenticating-to-github/keeping-your-account-and-data-secure/creating-a-personal-access-token>`_
must be created. The rights `repo` and `admin:org`  are required. Root dir must
point to the location hosting `/orgs/`

To apply changes in your organization repositories run:

.. code-block:: yaml

   ansible-playbook playbooks/run.yaml \
     -e github_repos_state=present \
     -e gitstyring_root_dir=../org \
     -e gitub_token=SECRET

Testing
-------

Testing of the collection locally can be done with the help of ansible-test
utility. For that (under assumption of proper checkout location or setting
environment variables to include working directory) test invokation can be
executed as: `ansible-test integration members` or `ansible-test integration
members`.

Testing assumes local configuration is prepared in the
tests/integration/integration_config.yml` file:

.. code-block:: yaml

   root: "<CHECKOUT_DIRECTORY>/test_org"
   token: "<TESTING_TOKEN>"
