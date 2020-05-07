"""
    Copyright (C) 2017-2018 Team Kodi
    This file is part of Kodi - kodi.tv

    SPDX-License-Identifier: GPL-3.0-only
    See LICENSES/README.md for more information.
"""

import json
import os
import re
import xml.etree.ElementTree as ET

from . import handle_files
from .common import relative_path, get_debug_log_path, get_reporter_log_path
from .common.decorators import posix_only
from .record import INFORMATION, PROBLEM, WARNING, Record
from .report import Report


def check_for_invalid_xml_files(report: Report, file_index: list):
    """check if any xml file present in the addon is invalid or not
        :file_index: A list having all the name and path of files in
                        addons
    """
    for file in file_index:
        if ".xml" in file["name"]:
            xml_path = os.path.join(file["path"], file["name"])
            try:
                # Just try if we can successfully parse it
                ET.parse(xml_path)
            except ET.ParseError:
                report.add(Record(PROBLEM, "Invalid xml found. %s" %
                                  relative_path(xml_path)))


def check_for_invalid_json_files(report: Report, file_index: list):
    """ check if any json file present in the addon is invalid or not
        :file_index: A list having all the name and path of files in
                     addons
    """
    for file in file_index:
        if ".json" in file["name"]:
            path = os.path.join(file["path"], file["name"])
            try:
                # Just try if we can successfully parse it
                with open(path) as json_data:
                    json.load(json_data)
            except ValueError:
                report.add(Record(PROBLEM, "Invalid json found. %s" %
                                  relative_path(path)))


def check_addon_xml(report: Report, addon_path: str, parsed_xml, folder_id_mismatch: bool):
    """Check whether the addon.xml present in the addon is parseable or not
        :addon_path: path to the addon
        :parsed_xml: parsed tree for xml file
        :folder_id_mismatch: whether to allow folder and id mismatch
    """
    addon_xml_path = os.path.join(addon_path, "addon.xml")
    try:
        handle_files.addon_file_exists(report, addon_path, r"addon\.xml")

        report.add(Record(INFORMATION, "Created by %s" %
                          parsed_xml.attrib.get("provider-name")))
        addon_xml_matches_folder(report, addon_path, parsed_xml, folder_id_mismatch)
    except ET.ParseError:
        report.add(Record(PROBLEM, "Addon xml not valid, check xml. %s" %
                          relative_path(addon_xml_path)))

    return parsed_xml


def addon_xml_matches_folder(report: Report, addon_path: str, parsed_xml, folder_id_mismatch: bool):
    """Check if the name of the addon matches the folder in which the addon
    files are present
        :addon_path: path to the addon folder
        :addon_xml: parsed tree for xml file
        :folder_id_mismatch: whether to allow folder and id mismatch
    """
    addon_id = parsed_xml.attrib.get("id")
    if os.path.basename(os.path.normpath(addon_path)) == addon_id:
        report.add(Record(INFORMATION, "Addon id matches folder name"))
    else:
        if folder_id_mismatch:
            report.add(Record(INFORMATION, "Addon id and folder name does not match. "
                                           "Ensure folder name is {} when submitting a PR "
                                           "to Kodi's official repository.".format(addon_id)))
        else:
            report.add(Record(PROBLEM, "Addon id and folder name does not match."))


def check_for_new_language_directory_structure(report: Report, addon_path: str, supported=True):
    """Check whether the language directory structure is new or not
        :addon_path: path to addon folder
        :supported: if we should error out in case the new language format is not supported
        by the respective kodiversion
    """
    language_path = os.path.join(addon_path, "resources", "language")
    if os.path.exists(language_path):
        dirs = next(os.walk(language_path))[1]
        for directory in dirs:
            if "resource.language." not in directory and supported:
                report.add(Record(
                    PROBLEM, "Using the old language directory structure in %s, please move to the new one." %
                    os.path.join(language_path, directory)))
            elif "resource.language." in directory and not supported:
                report.add(Record(
                    PROBLEM, "Using the new language directory structure in %s for a Kodi version that does not" \
                             "support it. Please use the old language file struture or move the addon to" \
                             "an upper branch/kodi version." % os.path.join(language_path, directory)))


def check_file_whitelist(report: Report, file_index: list, addon_path: str, debug_log_enabled: bool, reporter_log_enabled: bool):
    """Check whether the files present in addon are in whitelist or not
        It ignores the .gitignore file and the log files generated by the tool
        (if the associated arguments are used).
        :file_index: list having names and path of all the files present in addon
        :addon_path: path to the addon folder
    """
    if ".module." in addon_path:
        report.add(Record(INFORMATION, "Module skipping whitelist"))
        return

    whitelist = (
        r"\.?(py|xml|gif|png|jpg|jpeg|md|txt|po|json|gitignore|markdown|yml|"
        r"rst|ini|flv|wav|mp4|html|css|lst|pkla|g|template|in|cfg|xsd|directory|"
        r"help|list|mpeg|pls|info|ttf|xsp|theme|yaml|dict|crt|ico)?$"
    )

    # Depending on the arguments used, ignore the log files
    files_to_ignore = []
    if debug_log_enabled:
        files_to_ignore.append(get_debug_log_path())
    if reporter_log_enabled:
        files_to_ignore.append(get_reporter_log_path())

    for file in file_index:
        if os.path.join(file["path"], file["name"]) not in files_to_ignore:
            file_parts = file["name"].rsplit(".")
            if len(file_parts) > 1:
                file_ending = "." + file_parts[len(file_parts) - 1]
                if re.match(whitelist, file_ending, re.IGNORECASE) is None:
                    report.add(Record(WARNING,
                                      "Found non whitelisted file ending in filename %s" %
                                      relative_path(os.path.join(file["path"], file["name"]))))


@posix_only
def check_file_permission(report: Report, file_index: list):
    """Check whether the files present in addon are marked executable
       or not
        :file_index: list having names and path of all the files present in addon
    """

    for file in file_index:
        file = os.path.join(file["path"], file["name"])
        if os.path.isfile(file) and os.access(str(file), os.X_OK):
            report.add(Record(PROBLEM, "%s is marked as stand-alone executable" % relative_path(str(file))))
