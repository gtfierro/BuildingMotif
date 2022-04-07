from dataclasses import dataclass
from typing import Optional

import rdflib

from buildingmotif.building_motif import BuildingMotif
from buildingmotif.dataclasses.template import Template
from buildingmotif.tables import DBTemplate
from buildingmotif.utils import get_building_motif


@dataclass
class TemplateLibrary:
    """Collection of Templates. This class mirrors DBTemplateLibrary."""

    _id: int
    _name: str
    _bm: BuildingMotif

    @classmethod
    def create(cls, name: str) -> "TemplateLibrary":
        """create new Template Library

        :param name: tl name
        :type name: str
        :return: new TemplateLibrary
        :rtype: TemplateLibrary
        """
        bm = get_building_motif()
        db_template_library = bm.table_con.create_db_template_library(name)

        return cls(_id=db_template_library.id, _name=db_template_library.name, _bm=bm)

    @classmethod
    def load(cls, id: int) -> "TemplateLibrary":
        """load Template Library from db

        :param id: id of template library
        :type id: int
        :return: TemplateLibrary
        :rtype: TemplateLibrary
        """
        bm = get_building_motif()
        db_template_library = bm.table_con.get_db_template_library(id)

        return cls(_id=db_template_library.id, _name=db_template_library.name, _bm=bm)

    @property
    def id(self) -> Optional[int]:
        return self._id

    @id.setter
    def id(self, new_id):
        raise AttributeError("Cannot modify db id")

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, new_name: str):
        self._bm.table_con.update_db_template_library_name(self._id, new_name)
        self._name = new_name

    def create_template(self, name: str) -> Template:
        """Create Template in this Template Library

        :param name: name
        :type name: str
        :return: created Template
        :rtype: Template
        """
        db_template = self._bm.table_con.create_db_template(name, self._id)
        body = self._bm.graph_con.create_graph(db_template.body_id, rdflib.Graph())

        return Template(
            _id=db_template.id, _name=db_template.name, body=body, _bm=self._bm
        )

    def get_templates(self) -> list[Template]:
        """get Templates in Library

        :return: list of templates
        :rtype: list[Template]
        """
        db_template_library = self._bm.table_con.get_db_template_library(self._id)
        templates: list[DBTemplate] = db_template_library.templates
        return [Template.load(t.id) for t in templates]
