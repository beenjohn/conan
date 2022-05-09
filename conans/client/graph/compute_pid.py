from collections import OrderedDict

from conans.client.graph.graph import BINARY_INVALID, BINARY_ERROR
from conans.errors import conanfile_exception_formatter, ConanInvalidConfiguration, \
    ConanErrorConfiguration, conanfile_remove_attr
from conans.model.info import ConanInfo, RequirementsInfo, RequirementInfo, PythonRequiresInfo


def compute_package_id(node, new_config):
    """
    Compute the binary package ID of this node
    """
    conanfile = node.conanfile

    unknown_mode = new_config.get("core.package_id:default_unknown_mode", default="semver_mode")
    non_embed_mode = new_config.get("core.package_id:default_non_embed_mode", default="minor_mode")
    # recipe_revision_mode already takes into account the package_id
    embed_mode = new_config.get("core.package_id:default_embed_mode", default="full_mode")
    python_mode = new_config.get("core.package_id:default_python_mode", default="minor_mode")
    build_mode = new_config.get("core.package_id:default_build_mode", default=None)

    python_requires = getattr(conanfile, "python_requires", None)
    if python_requires:
        python_requires = python_requires.all_refs()

    data = OrderedDict()
    build_data = OrderedDict()
    for require, transitive in node.transitive_deps.items():
        dep_node = transitive.node
        require.deduce_package_id_mode(conanfile.package_type, dep_node.conanfile.package_type,
                                       non_embed_mode, embed_mode, build_mode, unknown_mode)
        if require.package_id_mode is not None:
            req_info = RequirementInfo(dep_node.pref.ref, dep_node.pref.package_id,
                                       require.package_id_mode)
            if require.build:
                build_data[require] = req_info
            else:
                data[require] = req_info

    reqs_info = RequirementsInfo(data)
    build_requires_info = RequirementsInfo(build_data)
    python_requires = PythonRequiresInfo(python_requires, python_mode)

    conanfile.info = ConanInfo(conanfile.settings.copy_conaninfo_settings(),
                               conanfile.options.copy_conaninfo_options(),
                               reqs_info,
                               build_requires_info,
                               python_requires=python_requires)
    conanfile.original_info = conanfile.info.clone()

    run_validate_package_id(conanfile)

    info = conanfile.info
    node.package_id = info.package_id()


def run_validate_package_id(conanfile):
    # IMPORTANT: This validation code must run before calling info.package_id(), to mark "invalid"
    if hasattr(conanfile, "validate"):
        with conanfile_exception_formatter(conanfile, "validate"):
            with conanfile_remove_attr(conanfile, ['cpp_info'], "validate"):
                try:
                    conanfile.validate()
                except ConanInvalidConfiguration as e:
                    conanfile.info.invalid = BINARY_INVALID, str(e)
                except ConanErrorConfiguration as e:
                    conanfile.info.invalid = BINARY_ERROR, str(e)

    # Once we are done, call package_id() to narrow and change possible values
    if hasattr(conanfile, "package_id"):
        with conanfile_exception_formatter(conanfile, "package_id"):
            with conanfile_remove_attr(conanfile, ['cpp_info'], "package_id"):
                conanfile.package_id()

    conanfile.info.validate()
