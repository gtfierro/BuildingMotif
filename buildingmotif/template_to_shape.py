from collections import Counter, defaultdict
from copy import copy
from dataclasses import dataclass, field
from itertools import chain
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from rdflib import BNode, Graph, Literal, URIRef
from rdflib.term import Node

from buildingmotif.namespaces import PARAM, RDF, SH, bind_prefixes
from buildingmotif.utils import copy_graph, validate_uri

if TYPE_CHECKING:
    from buildingmotif.dataclasses import Template


def _add_property_shape(
    graph: Graph,
    name: Node,
    constraint: Optional[Node],
    path: Node,
    value: Optional[Node],
    exact_count: int = 1,
):
    pshape = BNode()
    graph.add((name, SH.property, pshape))
    graph.add((pshape, SH.path, path))
    if constraint is not None and value is not None:
        graph.add((pshape, constraint, value))
    graph.add((pshape, SH["minCount"], Literal(exact_count)))
    # if exact_count > 0:
    #    graph.add((pshape, SH["maxCount"], Literal(exact_count)))


def _add_qualified_property_shape(
    graph: Graph,
    name: Node,
    constraint: Node,
    path: Node,
    value: Node,
    exact_count: int = 1,
):
    pshape = BNode()
    graph.add((name, SH.property, pshape))
    graph.add((pshape, SH.path, path))
    qvc = BNode()
    graph.add((pshape, SH["qualifiedValueShape"], qvc))
    graph.add((qvc, constraint, value))
    graph.add((pshape, SH["qualifiedMinCount"], Literal(exact_count)))
    # if exact_count > 0:
    #    graph.add((pshape, SH["qualifiedMaxCount"], Literal(exact_count)))


@dataclass
class _OptNodeList:
    required: List[Node] = field(default_factory=list)
    optional: List[Node] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.required) + len(self.optional)

    @property
    def counts(self) -> Dict[Node, int]:
        c = Counter(self.required)
        for k in self.optional:
            c[k] = max(c[k], 0)
        return c

    @property
    def first(self) -> Tuple[Node, int]:
        return next(iter(self.counts.items()))

    def remove(self, node: Node):
        if node in self.required:
            self.required.remove(node)
        if node in self.optional:
            self.optional.remove(node)

    def __iter__(self):
        # aggregate by type
        c_required = Counter(self.required)
        c_optional = Counter(self.optional)
        for k, v in list(c_optional.items()):
            if k in c_required:
                c_required[k] = min(c_required[k], v)
                del c_optional[k]
        return chain.from_iterable(
            [
                c_required.items(),
                c_optional.items(),
            ]
        )


@dataclass
class _TemplateIndex:
    template: "Template"
    param_types: Dict[Node, List[Node]]
    prop_types: Dict[Node, _OptNodeList]
    prop_values: Dict[Node, List[Node]]
    prop_shapes: Dict[Node, _OptNodeList]
    prop_unspecific: _OptNodeList
    target: URIRef

    @property
    def target_type(self):
        return self.param_types.get(self.target, [None])[0]

    def add_to_shape(self, shape: Graph):
        """
        Adds this template index in its shape form
        into the provided graph
        """
        self._resolve_property_shapes()
        self._add_prop_types_to_shape(shape)
        self._add_prop_shapes_to_shape(shape)
        self._add_prop_values_to_shape(shape)
        self._add_unspecific_props_to_shape(shape)

    def _resolve_property_shapes(self):
        """
        Compresses the chains of items in each of the prop_* dictionaries
        to avoid contradictory or redundant information
        """
        # remove 'unspecified' props from prop_unspecific if they have
        # definitions elsewhere
        self.specified_props = Counter()
        self.specified_props.update(self.prop_types.keys())
        self.specified_props.update(self.prop_values.keys())
        self.specified_props.update(self.prop_shapes.keys())
        for prop in self.specified_props:
            self.prop_unspecific.remove(prop)
        self.specified_props.update(self.prop_unspecific)
        # new_prop_types: Dict[Node, _OptNodeList] = dict()
        # for prop, ptypes in self.prop_types.items():
        #    c_required = Counter([x for x in ptypes.required])
        #    c_optional = Counter([x for x in ptypes.optional])
        #    for k, v in list(c_optional.items()):
        #        if k in c_required:
        #            c_required[k] = min(c_required[k], v)
        #            del c_optional[k]
        #    # at this point, c_required aggregates all of the optional props
        #    # that also show up in required. c_optional only contains optional shapes now
        #    new_prop_types[prop] = _OptNodeList()
        #    new_prop_types[prop].required = list(
        #        chain.from_iterable(
        #            repeat(item, count) for item, count in c_required.items()
        #        )
        #    )
        #    new_prop_types[prop].optional = list(
        #        chain.from_iterable(
        #            repeat(item, count) for item, count in c_optional.items()
        #        )
        #    )
        # self.prop_types = new_prop_types

    def _add_prop_types_to_shape(self, shape: Graph):
        """
        Adds the prop_types index to the graph containing the shape
        """
        for prop, ptypes in self.prop_types.items():
            c = Counter(
                ptypes
            )  # count by type; if there is more than 1 type for this prop, use qualified
            if len(c) == 1 and self.specified_props[prop] == 1:
                ptype, mincount = ptypes.first
                _add_property_shape(
                    shape, PARAM[self.template.name], SH["class"], prop, ptype, mincount
                )
            else:
                for ptype, mincount in ptypes.counts.items():
                    _add_qualified_property_shape(
                        shape,
                        PARAM[self.template.name],
                        SH["class"],
                        prop,
                        ptype,
                        mincount,
                    )

    def _add_prop_shapes_to_shape(self, shape: Graph):
        """
        Adds the prop_shapes index to the graph containing the shape
        """
        for prop, ptypes in self.prop_shapes.items():
            c = Counter(
                ptypes
            )  # count by type; if there is more than 1 type for this prop, use qualified
            if len(c) == 1 and self.specified_props[prop] == 1:
                ptype, mincount = ptypes.first
                _add_property_shape(
                    shape, PARAM[self.template.name], SH["node"], prop, ptype, mincount
                )
            else:
                for ptype, mincount in ptypes.counts.items():
                    _add_qualified_property_shape(
                        shape,
                        PARAM[self.template.name],
                        SH["node"],
                        prop,
                        ptype,
                        mincount,
                    )

    def _add_prop_values_to_shape(self, shape: Graph):
        """
        Adds the prop_values index to the graph containing the shape
        """
        for prop, values in self.prop_values.items():
            c = Counter(
                values
            )  # count by type; if there is more than 1 type for this prop, use qualified
            if len(c) == 1 and self.specified_props[prop] == 1:
                _add_property_shape(
                    shape, PARAM[self.template.name], SH.hasValue, prop, values[0]
                )
            else:  # more than one ptype
                for value in values:
                    _add_qualified_property_shape(
                        shape, PARAM[self.template.name], SH.hasValue, prop, value
                    )

    def _add_unspecific_props_to_shape(self, shape: Graph):
        for (prop, mincount) in self.prop_unspecific:
            _add_property_shape(
                shape, PARAM[self.template.name], None, prop, None, mincount
            )


def _prep_shape_graph() -> Graph:
    shape = Graph()
    bind_prefixes(shape)
    shape.bind("p", PARAM)
    return shape


def _index_properties(templ: "Template", target: URIRef) -> _TemplateIndex:
    templ_graph = copy_graph(templ.body)

    # store the classes for each parameter
    param_types: Dict[Node, List[Node]] = defaultdict(list)
    for (param, ptype) in templ_graph.subject_objects(RDF.type):
        param_types[param].append(ptype)

    # store the properties and their types for the target
    prop_types: Dict[Node, _OptNodeList] = defaultdict(_OptNodeList)
    prop_values: Dict[Node, List[Node]] = defaultdict(list)
    prop_shapes: Dict[Node, _OptNodeList] = defaultdict(_OptNodeList)
    prop_unspecific: _OptNodeList = _OptNodeList()
    # TODO: prop_shapes for all properties whose object corresponds to another shape
    for p, o in templ_graph.predicate_objects(target):
        if p == RDF.type:
            continue
        if str(o).startswith(PARAM) and not str(p).startswith(PARAM):
            # handle the case where the object is a parameter but the
            # predicate is not. This will be a property shape with the
            # predicate as the sh:path.

            # If there's a dependency, use sh:node to refer to that shape
            param_name = str(o)[len(PARAM) :]
            dep_templ = templ.dependency_for_parameter(param_name)
            if dep_templ is not None:
                # determine which shape list we are inserting into;
                # if the parameter is optional, put it in the optional list;
                # else put it in the required list
                shape_list = prop_shapes[p].required
                if param_name in templ.optional_args:
                    shape_list = prop_shapes[p].optional

                # use the template name directly if it is a URI, else put it into the PARAM
                # namespace to easily convert it to a URI
                try:
                    validate_uri(dep_templ.name)
                    shape_list.append(URIRef(dep_templ.name))
                except ValueError:
                    dep_templ_shape_name = PARAM[dep_templ.name]
                    shape_list.append(dep_templ_shape_name)

            # Otherwise, if "{o} rdf:type {class}" exists within the graph, then
            # we can associate an sh:class with that type
            o_class = templ_graph.value(o, RDF.type)
            if o_class is not None:
                # determine which type list we are inserting into;
                # if the parameter is optional, put it in the optional list;
                # else put it in the required list
                type_list = prop_types[p].required
                if param_name in templ.optional_args:
                    type_list = prop_types[p].optional
                type_list.append(o_class)
            else:
                unspecific_list = prop_unspecific.required
                if param_name in templ.optional_args:
                    unspecific_list = prop_unspecific.optional
                # if there is no RDF.type and 'o' is not referenced in a dependency,
                # then ther are no restrictions on its type and we can
                # add a more permissive PropertyShape
                unspecific_list.append(p)
        else:
            # o is not a PARAM, so use hasValue
            prop_values[p].append(o)

    return _TemplateIndex(
        templ,
        dict(param_types),
        dict(prop_types),
        dict(prop_values),
        dict(prop_shapes),
        prop_unspecific,
        target,
    )


def template_to_nodeshape(template: "Template") -> Graph:
    """
    Interprets the template body as a SHACL shape and returns the SHACL
    shape in its own graph. Uses the following rules to perform the transformation:
    - Generate a SHACL Node Shape
    - the P:name parameter is considered the 'root' of the shape; only
      the properties on the P:name-rooted subgraph will be put into the SHACL shape
    - Add a sh:class property pointing to the object of the 'P:name rdf:type ?class'
      edge in the template
    - for each other predicate of P:name in the template, generate a Property Shape:
      - if there is more than one object for a given predicate, use qualified* SHACL
        properties, else use the normal varieties
      - if the object of the predicate is a parameter (in the PARAM namespace), then
        generate a PropertyShape with sh:class (if an <object> rdf:type <object_type>
        edge exists in the template) or with sh:node (if the object parameter is
        referenced by a template dependency)
      - if the object is a paramater and is optional, make sure the minCount is 0,
        else default to 1
      - if the object of the predicate is *not* a parameter, use sh:hasValue

    :return: a graph containing the NodeShape
    :rtype: rdflib.Graph
    """
    # TODO If 'use_all' is True, this will create a shape that incorporates all
    # Templates by the same name in the same Library.
    templ = copy(template)
    shape = _prep_shape_graph()

    # create an index for the 'name' parameter -- this is the root of the template.
    # Make sure to inline_dependencies so that the full context is captured when generating
    # the shape
    idx: _TemplateIndex = _index_properties(templ.inline_dependencies(), PARAM["name"])
    # TODO: don't add targetClass for now...maybe there is some case where we want it?
    shape.add((PARAM[templ.name], RDF.type, SH.NodeShape))
    if idx.target_type is not None:
        shape.add((PARAM[templ.name], SH["class"], idx.target_type))
    idx.add_to_shape(shape)

    # find all other ?x rdf:type ?class nodes in the template that don't start with 'name'
    # and make sure to add them too
    for sub_templ in templ.body.objects(RDF.type):
        assert isinstance(sub_templ, URIRef)
        if sub_templ == PARAM["name"]:
            continue
        sub_idx: _TemplateIndex = _index_properties(templ, sub_templ)
        shape.add((sub_templ, RDF.type, SH.NodeShape))
        if sub_idx.target_type is not None:
            shape.add((sub_templ, SH["class"], sub_idx.target_type))
        sub_idx.add_to_shape(shape)

    # create the shape
    return shape