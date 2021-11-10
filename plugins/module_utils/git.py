# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type


import abc

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.urls import fetch_url


def base_argument_spec(**kwargs):
    spec = dict(
    )
    spec.update(kwargs)
    return spec


class GitBase:

    argument_spec = {}
    module_kwargs = {}
    _bp_templates = {}

    def __init__(self):

        self.ansible = AnsibleModule(
            base_argument_spec(**self.argument_spec),
            **self.module_kwargs)
        self.params = self.ansible.params
        self.module_name = self.ansible._name
        self.results = {'changed': False}
        self.errors = []
        self.exit = self.exit_json = self.ansible.exit_json
        self.fail = self.fail_json = self.ansible.fail_json

    @abc.abstractmethod
    def run(self):
        pass

    def __call__(self):
        """Execute `run` function when calling the class.
        """
        try:
            results = self.run()
            if results and isinstance(results, dict):
                self.ansible.exit_json(**results)
        except Exception as ex:
            self.ansible.fail_json(
                msg='Unhandled exception during execution',
                errors=self.errors,
                exception=ex
            )

    def save_error(self, msg):
        self.ansible.log(msg)
        self.errors.append(msg)

    def _prepare_graphql_query(self, query, variables):
        data = {
            'query': query,
            'variables': variables,
        }
        return data

    def _request(self, method, url, headers=None, **kwargs):
        if not headers:
            headers = dict()

        json_data = kwargs.pop('json', '')
        if json_data:
            kwargs['data'] = self.ansible.jsonify(json_data)

        response, info = fetch_url(
            module=self.ansible,
            headers=headers,
            method=method, url=url,
            **kwargs
        )
        content = ""
        if response:
            content = response.read()
        return (content, response, info)
