import inspect
from .plugin import (
    AbstractType,
    ConcreteType,
    Wrapper,
    Translator,
    AbstractAlgorithm,
    ConcreteAlgorithm,
)


class PluginRegistryError(Exception):
    pass


class PluginRegistry:
    """
    PluginRegistry for use by libraries implementing new types, translators, and algorithms for metagraph.
    Example Usage
    -------------
    # /plugins.py
    registry = metagraph.plugin_registry.PluginRegistry()
    def find_plugins():
        # Import modules here to ensure they are registered, but avoid circular imports
        from . import my_types, my_translators, my_algorithms
        return registry.plugins
    # Add entry_points to setup.py
    setup(
        ...
        entry_points={"metagraph.plugins": "plugins = plugins:find_plugins"},
        ...
    )
    # /my_types.py
    from .plugins import registry
    from metagraph import AbstractType, Wrapper
    @registry.register
    class MyCustomType(AbstractType):
        pass
    @registry.register
    class MyWrapper(Wrapper, abstract=MyCustomType):
        allowed_props = {'flag'}
        def __init__(self, value, flag=True):
            self.value = value
            self.flag = flag
    # /my_translators.py
    from .plugins import registry
    from .my_types import MyWrapper
    from metagraph import translator
    import networkx as nx
    @translator(registry=registry)
    def nx_to_mycustom(x: nx.Graph, **props) -> MyWrapper:
        # modify x
        return MyWrapper(x, flag=False)
    # /my_algorithms.py
    from .plugins import registry
    from .my_types import MyWrapper
    from metagraph import abstract_algorithm, concrete_algorithm
    import metagraph as mg
    # Create an abstract algorithm
    @abstract_algorithm('link_analysis.CustomPageRank', registry=registry)
    def custpr(g: Graph) -> Vector:
        pass
    @concrete_algorithm('link_analysis.CustomPageRank', registry=registry)
    def mycustpr(g: MyWrapper) -> mg.types.NumpyVector:
        result = ...
        return results
    """

    def __init__(self):
        self.plugins = {
            "abstract_types": set(),
            "concrete_types": set(),
            "wrappers": set(),
            "translators": set(),
            "abstract_algorithms": set(),
            "concrete_algorithms": set(),
        }

    def register(self, obj):
        """
        Decorate classes and functions to include them in the registry
        """
        unknown = False
        if type(obj) is type:
            if issubclass(obj, AbstractType):
                self.plugins["abstract_types"].add(obj)
            elif issubclass(obj, ConcreteType):
                self.plugins["concrete_types"].add(obj)
            elif issubclass(obj, Wrapper):
                self.plugins["wrappers"].add(obj)
            else:
                unknown = True
        else:
            if isinstance(obj, Translator):
                self.plugins["translators"].add(obj)
            elif isinstance(obj, AbstractAlgorithm):
                self.plugins["abstract_algorithms"].add(obj)
            elif isinstance(obj, ConcreteAlgorithm):
                self.plugins["concrete_algorithms"].add(obj)
            else:
                unknown = True

        if unknown:
            raise PluginRegistryError(
                f"Invalid object for plugin registry: {type(obj)}"
            )
        return obj

    def register_from_modules(self, *modules, recurse=True):
        """
        Find and register all suitable objects within modules.

        This only includes objects created within a module or one of its submodules.
        Objects whose names begin with `_` are skipped.

        If ``recurse`` is True, then also recurse into any submodule we find.
        """
        if len(modules) == 1 and isinstance(modules[0], (list, tuple)):
            modules = modules[0]
        for module in modules:
            if not inspect.ismodule(module):
                raise TypeError(
                    f"Expected one or more modules.  Got a type {type(module)} instead."
                )

        # If requested, we could break this out into a function that yields items.
        def _register_module(module, *, recurse, base_name, seen_modules):
            for key, val in vars(module).items():
                if key.startswith("_"):
                    continue
                if isinstance(val, type):
                    if (
                        issubclass(val, (Wrapper, ConcreteType, AbstractType))
                        and (
                            val.__module__ == base_name
                            or val.__module__.startswith(base_name + ".")
                        )
                        and val not in {Wrapper, ConcreteType, AbstractType}
                    ):
                        self.register(val)
                elif isinstance(
                    val, (Translator, ConcreteAlgorithm, AbstractAlgorithm)
                ):
                    # if val.__wrapped__.__module__.startswith(base_name):  # maybe?
                    self.register(val)
                elif (
                    recurse
                    and inspect.ismodule(val)
                    and val.__name__.startswith(base_name)
                    and val not in seen_modules
                ):
                    seen_modules.add(val)
                    _register_module(
                        val,
                        recurse=recurse,
                        base_name=base_name,
                        seen_modules=seen_modules,
                    )

        seen_modules = set()
        for module in sorted(modules, key=lambda x: x.__name__.count(".")):
            seen_modules.add(module)
            _register_module(
                module,
                recurse=recurse,
                base_name=module.__name__,
                seen_modules=seen_modules,
            )