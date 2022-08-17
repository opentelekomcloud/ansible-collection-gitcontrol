# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type


class ModuleDocFragment(object):

    # Standard documentation fragment
    DOCUMENTATION = r'''
options:
  token:
    description: Gitea token
    type: str
    required: True
  api_url:
    description: URL of the Gitiea API
    type: str
    required: True
requirements:
  - python >= 3.6
  - requests
'''
