from __future__ import annotations

import importlib
import pkgutil
import time
import types

from comfy.nodes import base_nodes as base_nodes
from comfy_extras import nodes as comfy_extras_nodes

try:
    import custom_nodes
except:
    custom_nodes = None
from comfy.nodes.package_typing import ExportedNodes
from functools import reduce

_comfy_nodes = ExportedNodes()


def _import_nodes_in_module(exported_nodes: ExportedNodes, module: types.ModuleType):
    node_class_mappings = getattr(module, 'NODE_CLASS_MAPPINGS', None)
    node_display_names = getattr(module, 'NODE_DISPLAY_NAME_MAPPINGS', None)
    if node_class_mappings:
        exported_nodes.NODE_CLASS_MAPPINGS.update(node_class_mappings)
    if node_display_names:
        exported_nodes.NODE_DISPLAY_NAME_MAPPINGS.update(node_display_names)


def _import_and_enumerate_nodes_in_module(module: types.ModuleType, print_import_times=False) -> ExportedNodes:
    exported_nodes = ExportedNodes()
    timings = []
    if hasattr(module, 'NODE_CLASS_MAPPINGS'):
        node_class_mappings = getattr(module, 'NODE_CLASS_MAPPINGS', None)
        node_display_names = getattr(module, 'NODE_DISPLAY_NAME_MAPPINGS', None)
        if node_class_mappings:
            exported_nodes.NODE_CLASS_MAPPINGS.update(node_class_mappings)
        if node_display_names:
            exported_nodes.NODE_DISPLAY_NAME_MAPPINGS.update(node_display_names)
    else:
        # Iterate through all the submodules
        for _, name, is_pkg in pkgutil.iter_modules(module.__path__):
            full_name = module.__name__ + "." + name
            time_before = time.perf_counter()
            success = True

            if full_name.endswith(".disabled"):
                continue
            try:
                submodule = importlib.import_module(full_name)
                # Recursively call the function if it's a package
                exported_nodes.update(
                    _import_and_enumerate_nodes_in_module(submodule, print_import_times=print_import_times))
            except KeyboardInterrupt as interrupted:
                raise interrupted
            except Exception as x:
                success = False
            timings.append((time.perf_counter() - time_before, full_name, success))

    if print_import_times and len(timings) > 0:
        for (duration, module_name, success) in sorted(timings):
            print(f"{duration:6.1f} seconds{'' if success else ' (IMPORT FAILED)'}, {module_name}")
    return exported_nodes


def import_all_nodes_in_workspace() -> ExportedNodes:
    if len(_comfy_nodes) == 0:
        base_and_extra = reduce(lambda x, y: x.update(y),
                                map(_import_and_enumerate_nodes_in_module, [
                                    # this is the list of default nodes to import
                                    base_nodes,
                                    comfy_extras_nodes
                                ]),
                                ExportedNodes())
        custom_nodes_mappings = ExportedNodes()
        if custom_nodes is not None:
            custom_nodes_mappings = _import_and_enumerate_nodes_in_module(custom_nodes, print_import_times=True)

            # don't allow custom nodes to overwrite base nodes
            custom_nodes_mappings -= base_and_extra

        _comfy_nodes.update(base_and_extra + custom_nodes_mappings)
    return _comfy_nodes
