# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type


class ModuleDocFragment(object):

    # Standard documentation fragment
    DOCUMENTATION = r'''
options:
  root:
    description:
      - Root path to the configuration location.
    type: str
    required: True
  github_url:
    description: URL of the GitHub API
    type: str
    default: https://api.github.com
requirements:
  - python >= 3.6
  - requests
'''
