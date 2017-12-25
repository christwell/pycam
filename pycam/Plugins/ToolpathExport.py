"""
Copyright 2011 Lars Kruse <devel@sumpfralle.de>

This file is part of PyCAM.

PyCAM is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

PyCAM is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with PyCAM.  If not, see <http://www.gnu.org/licenses/>.
"""

import datetime

from pycam import VERSION
import pycam.Gui.ControlsGTK
import pycam.Exporters.GCode.LinuxCNC
import pycam.Plugins
import pycam.workspace.data_models


FILTER_GCODE = (("GCode files", ("*.ngc", "*.nc", "*.gc", "*.gcode")),)


class ToolpathExport(pycam.Plugins.PluginBase):

    UI_FILE = "toolpath_export.ui"
    DEPENDS = ["Toolpaths", "FilenameDialog", "ExportSettings"]
    CATEGORIES = ["Toolpath", "Export"]

    def setup(self):
        self._last_toolpath_file = None
        if self.gui:
            self._frame = self.gui.get_object("ToolpathExportFrame")
            self._frame.unparent()
            self.core.register_ui("toolpath_handling", "Export", self._frame, -100)
            self._gtk_handlers = (
                (self.gui.get_object("ExportGCodeAll"), "clicked", self.export_all),
                (self.gui.get_object("ExportGCodeSelected"), "clicked", self.export_selected),
                (self.gui.get_object("ExportGCodeVisible"), "clicked", self.export_visible))
            self._event_handlers = (
                ("toolpath-list-changed", self._update_widgets),
                ("toolpath-selection-changed", self._update_widgets),
                ("toolpath-changed", self._update_widgets))
            self.register_gtk_handlers(self._gtk_handlers)
            self.register_event_handlers(self._event_handlers)
            self._update_widgets()
        return True

    def teardown(self):
        if self.gui:
            self.core.unregister_ui("toolpath_handling", self._frame)
            self.unregister_gtk_handlers(self._gtk_handlers)
            self.unregister_event_handlers(self._event_handlers)

    def _update_widgets(self):
        toolpaths = self.core.get("toolpaths")
        for name, filtered in (("ExportGCodeAll", toolpaths),
                               ("ExportGCodeVisible", toolpaths.get_visible()),
                               ("ExportGCodeSelected", toolpaths.get_selected())):
            self.gui.get_object(name).set_sensitive(bool(filtered))

    def export_all(self, widget=None):
        self._export_toolpaths(self.core.get("toolpaths").get_all())

    def export_visible(self, widget=None):
        self._export_toolpaths(self.core.get("toolpaths").get_visible())

    def export_selected(self, widget=None):
        self._export_toolpaths(self.core.get("toolpaths").get_selected())

    def _export_toolpaths(self, toolpaths):
        # we open a dialog
        # TODO: dynamically switch the dialog's filename extension with the selected export setting
        if self.core.get("gcode_filename_extension"):
            filename_extension = self.core.get("gcode_filename_extension")
        else:
            filename_extension = None
        # TODO: separate this away from Gui/Project.py
        # TODO: implement "last_model_filename" in core
        all_export_settings = self.core.get("export_settings")
        export_options_control = pycam.Gui.ControlsGTK.InputChoice(
            (item.get_application_value("name", item.get_id()), item.get_id())
            for item in all_export_settings)
        # Configure a change handler in order to memorize the selection of the user. There is no
        # simple other way of retrieving the result of the "extra_widget" from the
        # "get_filename_func" handler.
        selected_settings = {"active": export_options_control.get_value()}
        export_options_control.connect(
            "changed",
            lambda: selected_settings.update({"active": export_options_control.get_value()}))
        filename = self.core.get("get_filename_func")(
            "Save toolpath to ...", mode_load=False, type_filter=FILTER_GCODE,
            filename_templates=(self._last_toolpath_file, self.core.get("last_model_filename")),
            filename_extension=filename_extension,
            extra_widget=export_options_control.get_widget())
        if filename:
            self._last_toolpath_file = filename
        # no filename given -> exit
        if not filename:
            return
        export = pycam.workspace.data_models.Export(None, {
            "format": {"type": "gcode", "dialect": "linuxcnc",
                       "comment": ("Generated by PyCAM {}: {}"
                                   .format(VERSION, datetime.datetime.now().strftime("%Y-%m-%d"))),
                       "export_settings": selected_settings["active"]},
            "source": {"type": "toolpath",
                       "toolpaths": [tp.get_id() for tp in toolpaths]},
            "target": {"type": "file", "location": filename}})
        try:
            export.run_export()
        except IOError as err_msg:
            self.log.error("Failed to save toolpath file: %s", err_msg)
        else:
            # remove the temporary export item
            del export
            self.log.info("GCode file successfully written: %s", str(filename))
            self.core.emit_event("notify-file-saved", filename)
