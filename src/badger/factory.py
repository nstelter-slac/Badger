from badger.settings import init_settings
from badger.utils import get_value_or_none
from badger.errors import (
    BadgerConfigError,
    BadgerInvalidPluginError,
    BadgerInvalidDocsError,
    BadgerPluginNotFoundError,
)
import sys
import os
import importlib
import yaml
from xopt.generators import generators, get_generator_defaults

import logging

logger = logging.getLogger(__name__)

LOAD_LOCAL_ALGO = False
ALGO_EXCLUDED = [
    "bayesian_exploration",
    "cnsga",
    "mggpo",
    "time_dependent_upper_confidence_bound",
    "multi_fidelity",
    "nsga2",
]

# Check badger plugin root
"""
config_singleton = init_settings()

BADGER_PLUGIN_ROOT = config_singleton.read_value("BADGER_PLUGIN_ROOT")
if BADGER_PLUGIN_ROOT is None:
    raise BadgerConfigError("Please set the BADGER_PLUGIN_ROOT env var!")
elif not os.path.exists(BADGER_PLUGIN_ROOT):
    raise BadgerConfigError(
        f"The badger plugin root {BADGER_PLUGIN_ROOT} does not exist!"
    )
else:
    module_file = os.path.join(BADGER_PLUGIN_ROOT, "__init__.py")
    if not os.path.exists(module_file):
        with open(module_file, "w") as f:
            pass
sys.path.append(BADGER_PLUGIN_ROOT) """

# Don't initialize at module load time!
_config_singleton = None
_BADGER_PLUGIN_ROOT = None
_BADGER_FACTORY = None
_BADGER_EXTENSIONS = None


def _get_config():
    """Get the config singleton, initializing it lazily if needed."""
    global _config_singleton
    if _config_singleton is None:
        _config_singleton = init_settings()
    return _config_singleton


def _get_plugin_root():
    """Get BADGER_PLUGIN_ROOT, initializing and validating it lazily."""
    global _BADGER_PLUGIN_ROOT
    
    if _BADGER_PLUGIN_ROOT is None:
        config = _get_config()
        _BADGER_PLUGIN_ROOT = config.read_value("BADGER_PLUGIN_ROOT")
        
        if _BADGER_PLUGIN_ROOT is None:
            raise BadgerConfigError("Please set the BADGER_PLUGIN_ROOT env var!")
        elif not os.path.exists(_BADGER_PLUGIN_ROOT):
            raise BadgerConfigError(
                f"The badger plugin root {_BADGER_PLUGIN_ROOT} does not exist!"
            )
        else:
            module_file = os.path.join(_BADGER_PLUGIN_ROOT, "__init__.py")
            if not os.path.exists(module_file):
                with open(module_file, "w") as f:
                    pass
        
        # Add to path only once
        if _BADGER_PLUGIN_ROOT not in sys.path:
            sys.path.append(_BADGER_PLUGIN_ROOT)
    
    return _BADGER_PLUGIN_ROOT


def _get_factory():
    """Get BADGER_FACTORY, scanning plugins lazily if needed."""
    global _BADGER_FACTORY
    
    if _BADGER_FACTORY is None:
        root = _get_plugin_root()
        _BADGER_FACTORY = scan_plugins(root)
    
    return _BADGER_FACTORY


def _get_extensions():
    """Get BADGER_EXTENSIONS, scanning lazily if needed."""
    global _BADGER_EXTENSIONS
    
    if _BADGER_EXTENSIONS is None:
        root = _get_plugin_root()
        _BADGER_EXTENSIONS = scan_extensions(root)
    
    return _BADGER_EXTENSIONS


def scan_plugins(root):
    factory = {}

    # Do not scan local generators if option disabled
    if LOAD_LOCAL_ALGO:
        ptype_list = ["generator", "interface", "environment"]
    else:
        ptype_list = ["interface", "environment"]
        factory["generator"] = {}

    for ptype in ptype_list:
        factory[ptype] = {}

        proot = os.path.join(root, f"{ptype}s")

        try:
            plugins = [
                fname
                for fname in os.listdir(proot)
                if os.path.exists(os.path.join(proot, fname, "__init__.py"))
            ]
        except:
            plugins = []

        for pname in plugins:
            # TODO: Also load the configs here
            # So that list plugins can access the metadata of the plugins
            factory[ptype][pname] = None

    return factory


def load_plugin(root, pname, ptype):
    assert ptype in [
        "generator",
        "interface",
        "environment",
    ], f"Invalid plugin type {ptype}"

    proot = os.path.join(root, f"{ptype}s")

    # Load the params in the configs
    configs = None
    with open(os.path.join(proot, pname, "configs.yaml"), "r") as f:
        try:
            configs = yaml.safe_load(f)
        except yaml.YAMLError:
            raise BadgerInvalidPluginError(
                f"Error loading plugin {ptype} {pname}: invalid config"
            )

    # Load module
    try:
        module = importlib.import_module(f"{ptype}s.{pname}")
    except ImportError as e:
        _e = BadgerInvalidPluginError(
            f"{ptype} {pname} is not available due to missing dependencies: {e}"
        )
        _e.configs = configs  # attach information to the exception
        raise _e

    if ptype == "generator":
        plugin = [module.optimize, configs]
    elif ptype == "interface":
        params = module.Interface.model_json_schema()["properties"]
        params = {
            name: get_value_or_none(info, "default") for name, info in params.items()
        }
        configs["params"] = params
        plugin = [module.Interface, configs]
    elif ptype == "environment":
        vars = module.Environment.variables
        obses = module.Environment.observables
        params = module.Environment.model_json_schema()["properties"]
        params = {
            name: get_value_or_none(info, "default")
            for name, info in params.items()
            if name != "interface"
        }
        # Get vranges by creating an env instance
        try:
            intf_name = configs["interface"][0]
            Interface, _ = get_intf(intf_name)
            intf = Interface()
        except KeyError:
            intf = None
        except Exception as e:
            logger.warning(e)
            intf = None
        env = module.Environment(interface=intf, params=configs)
        var_bounds = env.get_bounds(vars)

        vars_info = []
        for var in vars:
            var_info = {}
            var_info[var] = var_bounds[var]
            vars_info.append(var_info)

        configs["params"] = params
        configs["variables"] = vars_info
        configs["observations"] = obses
        plugin = [module.Environment, configs]
    else:  # TODO: raise an exception here instead?
        return [None, None]

    #BADGER_FACTORY[ptype][pname] = plugin
    factory = _get_factory()  # Changed from BADGER_FACTORY
    factory[ptype][pname] = plugin

    return plugin


def load_docs(root, pname, ptype):
    assert ptype in [
        "generator",
        "interface",
        "environment",
    ], f"Invalid plugin type {ptype}"

    proot = os.path.join(root, f"{ptype}s")

    # Load the readme and the docs
    readme = None
    docstring = None

    try:
        try:
            with open(os.path.join(proot, pname, "README.md"), "r") as f:
                readme = f.read()
        except:
            readme = f"# {pname}\nNo readme found.\n"

        module = importlib.import_module(f"{ptype}s.{pname}")
        docstring = module.Environment.__doc__

        # Format as Markdown code block
        help_md = f"```text\n{readme}\n# Environment Documentation\n{docstring}\n```"
        return help_md
    except:
        raise BadgerInvalidDocsError(
            f"Error loading docs for {ptype} {pname}: docs not found"
        )


def get_plug(root, name, ptype):
    factory = _get_factory() 
    try:
        plug = factory[ptype][name]
        #plug = BADGER_FACTORY[ptype][name]
        if plug is None:  # lazy loading
            plug = load_plugin(root, name, ptype)
            factory[ptype][name] = plug
            #BADGER_FACTORY[ptype][name] = plug
        # Prevent accidentially modifying default configs
        plug = [plug[0], plug[1].copy()]
    except KeyError:
        raise BadgerPluginNotFoundError(
            f"Error loading plugin {ptype} {name}: plugin not found"
        )

    return plug


def scan_extensions(root):
    extensions = {}

    return extensions


def get_generator_docs(name):
    return generators[name].__doc__


def get_env_docs(name):
    root = _get_plugin_root()  # Changed from BADGER_PLUGIN_ROOT
    return load_docs(root, name, "environment")
    #return load_docs(BADGER_PLUGIN_ROOT, name, "environment")


def get_intf(name):
    root = _get_plugin_root()  # Changed from BADGER_PLUGIN_ROOT
    return get_plug(root, name, "interface")
    #return get_plug(BADGER_PLUGIN_ROOT, name, "interface")


def get_env(name):
    root = _get_plugin_root()  # Changed from BADGER_PLUGIN_ROOT
    return get_plug(root, name, "environment")
    #return get_plug(BADGER_PLUGIN_ROOT, name, "environment")


def list_generators():
    try:
        from xopt.generators import try_load_all_generators

        try_load_all_generators()
    except ImportError:  # this API changed somehow
        pass  # there is nothing we can do...
    generator_names = list(generators.keys())
    # Filter the names
    generator_names = [n for n in generator_names if n not in ALGO_EXCLUDED]
    return sorted(generator_names)


get_generator = get_generator_defaults


def list_intf():
    factory = _get_factory()  # Changed from BADGER_FACTORY
    return sorted(factory["interface"])
    #return sorted(BADGER_FACTORY["interface"])


def list_env():
    factory = _get_factory()  # Changed from BADGER_FACTORY
    return sorted(factory["environment"])
    #return sorted(BADGER_FACTORY["environment"])


#BADGER_FACTORY = scan_plugins(BADGER_PLUGIN_ROOT)
#BADGER_EXTENSIONS = scan_extensions(BADGER_PLUGIN_ROOT)

# For backward compatibility - these trigger initialization when accessed
@property
def BADGER_PLUGIN_ROOT():
    return _get_plugin_root()

@property
def BADGER_FACTORY():
    return _get_factory()

@property  
def BADGER_EXTENSIONS():
    return _get_extensions()