#!/usr/bin/python3

import os

import yaml
from ansible.module_utils.basic import AnsibleModule


def main():
    module = AnsibleModule(
        argument_spec=dict(
            path=dict(type='str', required=True)
        )
    )

    output = {}
    for root, dirs, files in os.walk(module.params['path']):
        for file in [x for x in files if x.endswith(('.yml', '.yaml'))]:
            current_root = os.path.basename(root)
            a_yaml_file = open(os.path.join(root, file))
            parsed_yaml_file = yaml.safe_load(a_yaml_file)
            parent = os.path.basename(os.path.abspath(os.path.join(root, os.pardir)))
            if parent in output:
                if current_root in output[parent]:
                    output[parent][current_root].update(parsed_yaml_file)
                else:
                    output[parent].update({current_root: parsed_yaml_file})
            else:
                output.update({parent: {current_root: parsed_yaml_file}})
    module.exit_json(changed=True, data=output)


if __name__ == '__main__':
    main()
