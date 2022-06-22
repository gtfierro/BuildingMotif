from dataclasses import dataclass
from itertools import chain
from secrets import token_hex
from typing import TYPE_CHECKING, Dict, List, Optional, Set, Tuple, Union

import rdflib

from buildingmotif import get_building_motif
from buildingmotif.namespaces import bind_prefixes
from buildingmotif.utils import (
    PARAM,
    Term,
    copy_graph,
    remove_triples_with_node,
    replace_nodes,
)

if TYPE_CHECKING:
    from buildingmotif import BuildingMOTIF


@dataclass
class Template:
    """Template. This class mirrors DBTemplate."""

    _id: int
    _name: str
    body: rdflib.Graph
    optional_args: List[str]
    _bm: "BuildingMOTIF"

    @classmethod
    def load(cls, id: int) -> "Template":
        """load Template from db

        :param id: id of template
        :type id: int
        :return: loaded Template
        :rtype: Template
        """
        bm = get_building_motif()
        db_template = bm.table_connection.get_db_template(id)
        body = bm.graph_connection.get_graph(db_template.body_id)

        return cls(
            _id=db_template.id,
            _name=db_template.name,
            optional_args=db_template.optional_args,
            body=body,
            _bm=bm,
        )

    def in_memory_copy(self) -> "Template":
        """
        Return a copy of this template.
        """
        return Template(
            _id=-1,
            _name=self._name,
            body=copy_graph(self.body),
            optional_args=self.optional_args[:],
            _bm=self._bm,
        )

    @property
    def id(self):
        return self._id

    @id.setter
    def id(self, new_id):
        raise AttributeError("Cannot modify db id")

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, new_name: str) -> None:
        self._bm.table_connection.update_db_template_name(self._id, new_name)
        self._name = new_name

    def get_dependencies(self) -> Tuple["Dependency", ...]:
        return tuple(
            [
                Dependency(dep.dependee_id, dep.args)
                for dep in self._bm.table_connection.get_db_template_dependencies(
                    self._id
                )
            ]
        )

    def add_dependency(self, dependency: "Template", args: Dict[str, str]) -> None:
        self._bm.table_connection.add_template_dependency(self.id, dependency.id, args)

    def remove_dependency(self, dependency: "Template") -> None:
        self._bm.table_connection.remove_template_dependency(self.id, dependency.id)

    @property
    def parameters(self) -> Set[str]:
        """
        The set of all parameters used in this template, including its dependencies
        """
        # handle local parameters first
        nodes = chain.from_iterable(self.body.triples((None, None, None)))
        params = {str(p)[len(PARAM) :] for p in nodes if str(p).startswith(PARAM)}

        # then handle dependencies
        for dep in self.get_dependencies():
            params.update(dep.template.parameters)
        return params

    def dependency_for_parameter(self, param: str) -> Optional["Template"]:
        """
        Returns the dependency that uses the given parameter if one exists.

        :param param: parameter to search for
        :type param: str
        :return: dependency which uses the given parameter
        :rtype: Optional["Template"]
        """
        for dep in self.get_dependencies():
            if param in dep.args.values():
                return dep.template
        return None

    def to_inline(self, preserve_args: Optional[List[str]] = None) -> "Template":
        """
        Return an inline-able copy of this template by suffixing all parameters
        with a unique identifier which will avoid parameter name collisions when templates
        are combined with one another. Any argument names in the preserve_args list will
        not be adjusted

        :param preserve_args: parameters whose names will be preserved, defaults to None
        :type preserve_args: Optional[List[str]], optional
        :return: a template w/ globally unique parameters
        :rtype: "Template"
        """
        templ = self.in_memory_copy()
        suffix = f"{self.name}{token_hex(4)}-inlined"
        # the lookup table of old to new parameter names
        to_replace = {}
        for param in templ.parameters:
            # skip if (a) we want to preserve the param or (b) it is already inlined
            if (preserve_args and param in preserve_args) or (
                param.endswith("-inlined")
            ):
                continue
            param = PARAM[param]
            to_replace[param] = rdflib.URIRef(f"{param}-{suffix}")
        replace_nodes(templ.body, to_replace)
        return templ

    def inline_dependencies(self) -> "Template":
        """
        Returns a copy of this template with all dependencies recursively inlined

        :return: copy of this template with all dependencies inlined
        :rtype: "Template"
        """
        templ = self.in_memory_copy()
        if not self.get_dependencies():
            return templ

        for dep in self.get_dependencies():
            inlined_dep = dep.template.inline_dependencies()
            to_replace: Dict[rdflib.URIRef, Term] = {
                PARAM[theirs]: PARAM[ours] for ours, theirs in dep.args.items()
            }
            replace_nodes(inlined_dep.body, to_replace)
            # rewrite the names of all parameters in the dependency that aren't
            # mentioned in the dependent template
            preserved_params = list(dep.args.values())
            # concat bodies
            templ.body += inlined_dep.to_inline(preserved_params).body

        return templ

    def evaluate(
        self,
        bindings: Dict[str, Term],
        namespaces: Optional[Dict[str, rdflib.Namespace]] = None,
        require_optional_args: bool = False,
    ) -> Union["Template", rdflib.Graph]:
        """
        Evaluate the template with the provided bindings. If all parameters in the template
        have a provided binding, then a Graph will be returned. Otherwise, a new Template
        will be returned which incorporates the provided bindings and preserves unbound
        parameters. If require_optional_args is True, then the template evaluation will not return
        a Graph unless all optional arguments are bound. If require_optional_args is False, then
        the template evaluation will return a Graph even if some optional arguments are unbound.

        :param bindings: map of parameter name -> RDF term to substitute
        :type bindings: Dict[str, Term]
        :param namespaces: namespace bindings to add to the graph, defaults to None
        :type namespaces: Optional[Dict[str, rdflib.Namespace]], optional
        :param require_optional_args: whether to require all optional arguments to be bound,
                defaults to False
        :type require_optional_args: bool
        :return: either a template or a graph, depending on whether all parameters were provided
        :rtype: Union["Template", rdflib.Graph]
        """
        templ = self.in_memory_copy()
        uri_bindings = {PARAM[k]: v for k, v in bindings.items()}
        replace_nodes(templ.body, uri_bindings)
        # true if all parameters are now bound or only optional args are unbound
        if len(templ.parameters) == 0 or (
            not require_optional_args and templ.parameters == set(self.optional_args)
        ):
            bind_prefixes(templ.body)
            if namespaces:
                for prefix, namespace in namespaces.items():
                    templ.body.bind(prefix, namespace)
            if not require_optional_args:
                # remove all triples that touch unbound optional_args
                unbound_optional_args = set(templ.optional_args) - set(
                    uri_bindings.keys()
                )
                for arg in unbound_optional_args:
                    remove_triples_with_node(templ.body, PARAM[arg])
            return templ.body
        return templ

    def fill(self, ns: rdflib.Namespace) -> Tuple[Dict[str, Term], rdflib.Graph]:
        """
        Evaluates the template with autogenerated bindings w/n the given "ns" namespace.

        :param ns: namespace to contain the autogenerated entities
        :type ns: rdflib.Namespace
        :return: a tuple of the bindings used and the resulting graph
        :rtype: Tuple[Dict[str, Term], rdflib.Graph]
        """
        bindings = {param: ns[f"{param}_{token_hex(4)}"] for param in self.parameters}
        res = self.evaluate(bindings)
        assert isinstance(res, rdflib.Graph)
        return bindings, res


@dataclass
class Dependency:
    _template_id: int
    args: Dict[str, str]

    @property
    def template_id(self):
        return self._template_id

    @property
    def template(self) -> Template:
        return Template.load(self._template_id)
