# -*- coding: utf-8 -*-
#
# Copyright © Spyder Project Contributors
# Licensed under the terms of the MIT License
# (see spyder/__init__.py for details)

"""
New API for plugins.

All plugins in Spyder 5+ must inherit from the classes present in this file.
"""

from __future__ import annotations

# Standard library imports
from collections import OrderedDict
import inspect
import logging
import os
import os.path as osp
import sys
from typing import List, Optional, Union
import warnings

# Third party imports
from qtpy.QtCore import QObject, Qt, Signal, Slot
from qtpy.QtGui import QCursor
from qtpy.QtWidgets import QApplication, QMainWindow

# Local imports
from spyder.api.config.mixins import SpyderConfigurationObserver
from spyder.api.exceptions import SpyderAPIError
from spyder.api.fonts import SpyderFontType
from spyder.api.plugin_registration.mixins import SpyderPluginObserver
from spyder.api.widgets.main_widget import PluginMainWidget
from spyder.api.widgets.mixins import SpyderActionMixin
from spyder.api.widgets.mixins import SpyderWidgetMixin
from spyder.app.cli_options import get_options
from spyder.config.gui import get_color_scheme, get_font
from spyder.config.user import NoDefault
from spyder.utils.icon_manager import ima
from spyder.utils.image_path_manager import IMAGE_PATH_MANAGER

# Package imports
from .enum import Plugins
from ._old_api import SpyderPluginWidget


# Logging
logger = logging.getLogger(__name__)


class SpyderPluginV2(QObject, SpyderActionMixin, SpyderConfigurationObserver,
                     SpyderPluginObserver):
    """
    A Spyder plugin to extend functionality without a dockable widget.

    If you want to create a plugin that adds a new pane, please use
    SpyderDockablePlugin.
    """

    # --- API: Mandatory attributes ------------------------------------------
    # ------------------------------------------------------------------------
    # Name of the plugin that will be used to refer to it.
    # This name must be unique and will only be loaded once.
    NAME = None

    # --- API: Optional attributes ------------------------------------------
    # ------------------------------------------------------------------------
    # List of required plugin dependencies.
    # Example: [Plugins.Plots, Plugins.IPythonConsole, ...].
    # These values are defined in the `Plugins` class present in this file.
    # If a plugin is using a widget from another plugin, that other
    # must be declared as a required dependency.
    REQUIRES = []

    # List of optional plugin dependencies.
    # Example: [Plugins.Plots, Plugins.IPythonConsole, ...].
    # These values are defined in the `Plugins` class present in this file.
    # A plugin might be performing actions when connectiong to other plugins,
    # but the main functionality of the plugin does not depend on other
    # plugins. For example, the Help plugin might render information from
    # the Editor or from the Console or from another source, but it does not
    # depend on either of those plugins.
    # Methods in the plugin that make use of optional plugins must check
    # existence before using those methods or applying signal connections.
    OPTIONAL = []

    # This must subclass a `PluginMainContainer` for non dockable plugins that
    # create a widget, like a status bar widget, a toolbar, a menu, etc.
    # For non dockable plugins that do not define widgets of any kind this can
    # be `None`, for example a plugin that only exposes a configuration page.
    CONTAINER_CLASS = None

    # Name of the configuration section that's going to be
    # used to record the plugin's permanent data in Spyder
    # config system (i.e. in spyder.ini)
    CONF_SECTION = None

    # Use a separate configuration file for the plugin.
    CONF_FILE = True

    # Define configuration defaults if using a separate file.
    # List of tuples, with the first item in the tuple being the section
    # name and the second item being the default options dictionary.
    #
    # CONF_DEFAULTS_EXAMPLE = [
    #     ('section-name', {'option-1': 'some-value',
    #                       'option-2': True,}),
    #     ('another-section-name', {'option-3': 'some-other-value',
    #                               'option-4': [1, 2, 3],}),
    # ]
    CONF_DEFAULTS = None

    # Define configuration version if using a separate file
    #
    # IMPORTANT NOTES:
    # 1. If you want to *change* the default value of a current option, you
    #    need to do a MINOR update in config version, e.g. from 3.0.0 to 3.1.0
    # 2. If you want to *remove* options that are no longer needed or if you
    #    want to *rename* options, then you need to do a MAJOR update in
    #    version, e.g. from 3.0.0 to 4.0.0
    # 3. You don't need to touch this value if you're just adding a new option
    CONF_VERSION = None

    # Widget to be used as entry in Spyder Preferences dialog.
    CONF_WIDGET_CLASS = None

    # Some plugins may add configuration options for other plugins.
    # Example:
    # ADDITIONAL_CONF_OPTIONS = {'section': <new value to add>}
    ADDITIONAL_CONF_OPTIONS = None

    # Define additional configurable options (via a tab) to
    # another's plugin configuration page. All configuration tabs should
    # inherit from `SpyderPreferencesTab`.
    # Example:
    # ADDITIONAL_CONF_TABS = {'plugin_name': [<SpyderPreferencesTab classes>]}
    ADDITIONAL_CONF_TABS = None

    # Define custom layout classes that the plugin wantes to be registered.
    # THe custom classes should extend from
    #       `spyder.pluginsl.layout.api::BaseGridLayoutType`
    CUSTOM_LAYOUTS = []

    # Path for images relative to the plugin path
    # A Python package can include one or several Spyder plugins. In this case
    # the package may be using images from a global folder outside the plugin
    # folder
    IMG_PATH = None

    # Control the font size relative to the global fonts defined in Spyder
    MONOSPACE_FONT_SIZE_DELTA = 0
    INTERFACE_FONT_SIZE_DELTA = 0

    # Define context to store actions, toolbars, toolbuttons and menus.
    CONTEXT_NAME = None

    # Define if a plugin can be disabled in preferences.
    # If False, the plugin is considered "core" and therefore it cannot be
    # disabled. Default: True
    CAN_BE_DISABLED = True

    # Qt Web Widgets may be a heavy dependency for many packagers
    # (e.g. conda-forge)
    # We thus ask plugins to declare whether or not they need
    # web widgets to enhance the distribution of Spyder to users
    # https://github.com/spyder-ide/spyder/pull/22196#issuecomment-2189377043
    REQUIRE_WEB_WIDGETS = False

    # --- API: Signals -------------------------------------------------------
    # ------------------------------------------------------------------------
    # Signals here are automatically connected by the Spyder main window and
    # connected to the the respective global actions defined on it.
    sig_free_memory_requested = Signal()
    """
    This signal can be emitted to request the main application to garbage
    collect deleted objects.
    """

    sig_plugin_ready = Signal()
    """
    This signal can be emitted to reflect that the plugin was initialized.
    """

    sig_quit_requested = Signal()
    """
    This signal can be emitted to request the main application to quit.
    """

    sig_restart_requested = Signal()
    """
    This signal can be emitted to request the main application to restart.
    """

    sig_status_message_requested = Signal(str, int)
    """
    This signal can be emitted to request the main application to display a
    message in the status bar.

    Parameters
    ----------
    message: str
        The actual message to display.
    timeout: int
        The timeout before the message disappears.
    """

    sig_redirect_stdio_requested = Signal(bool)
    """
    This signal can be emitted to request the main application to redirect
    standard output/error when using Open/Save/Browse dialogs within widgets.

    Parameters
    ----------
    enable: bool
        Enable/Disable standard input/output redirection.
    """

    sig_exception_occurred = Signal(dict)
    """
    This signal can be emitted to report an exception from any plugin.

    Parameters
    ----------
    error_data: dict
        The dictionary containing error data. The expected keys are:
        >>> error_data= {
            "text": str,
            "is_traceback": bool,
            "repo": str,
            "title": str,
            "label": str,
            "steps": str,
        }

    Notes
    -----
    The `is_traceback` key indicates if `text` contains plain text or a
    Python error traceback.

    The `title` and `repo` keys indicate how the error data should
    customize the report dialog and Github error submission.

    The `label` and `steps` keys allow customizing the content of the
    error dialog.

    This signal is automatically connected to the main container/widget.
    """

    sig_mainwindow_resized = Signal("QResizeEvent")
    """
    This signal is emitted when the main window is resized.

    Parameters
    ----------
    resize_event: QResizeEvent
        The event triggered on main window resize.

    Notes
    -----
    To be used by plugins tracking main window size changes.
    """

    sig_mainwindow_moved = Signal("QMoveEvent")
    """
    This signal is emitted when the main window is moved.

    Parameters
    ----------
    move_event: QMoveEvent
        The event triggered on main window move.

    Notes
    -----
    To be used by plugins tracking main window position changes.
    """

    sig_unmaximize_plugin_requested = Signal((), (object,))
    """
    This signal is emitted to inform the main window that it needs to
    unmaximize the currently maximized plugin, if any.

    Parameters
    ----------
    plugin_instance: SpyderDockablePlugin
        Unmaximize plugin only if it is not `plugin_instance`.
    """

    sig_mainwindow_state_changed = Signal(object)
    """
    This signal is emitted when the main window state has changed (for
    instance, between maximized and minimized states).

    Parameters
    ----------
    window_state: Qt.WindowStates
        The window state.
    """

    sig_focused_plugin_changed = Signal(object)
    """
    This signal is emitted when the plugin with keyboard focus changes.

    Parameters
    ----------
    plugin: Optional[SpyderDockablePlugin]
        The plugin that currently has keyboard focus, or None if no dockable
        plugin has focus.
    """

    # ---- Private attributes
    # -------------------------------------------------------------------------
    # Define configuration name map for plugin to split configuration
    # among several files. See spyder/config/main.py
    _CONF_NAME_MAP = None

    def __init__(self, parent, configuration=None):
        super().__init__(parent)

        # This is required since the MRO of this class does not go up until to
        # SpyderPluginObserver and SpyderConfigurationObserver when using
        # super(), see https://fuhm.net/super-harmful/
        SpyderPluginObserver.__init__(self)
        SpyderConfigurationObserver.__init__(self)

        self._main = parent
        self._widget = None
        self._conf = configuration
        self._plugin_path = os.path.dirname(inspect.getfile(self.__class__))
        self._container = None
        self._added_toolbars = OrderedDict()
        self._actions = {}
        self.is_compatible = None
        self.is_registered = None
        self.main: QMainWindow = parent

        # Attribute used to access the action, toolbar, toolbutton and menu
        # registries
        self.PLUGIN_NAME = self.NAME

        if self.CONTAINER_CLASS is not None:
            self._container = container = self.CONTAINER_CLASS(
                name=self.NAME,
                plugin=self,
                parent=parent
            )

            if hasattr(container, '_setup'):
                container._setup()

            if isinstance(container, SpyderWidgetMixin):
                container.setup()
                container.update_actions()

            # Default signals to connect in main container or main widget.
            container.sig_free_memory_requested.connect(
                self.sig_free_memory_requested)
            container.sig_quit_requested.connect(self.sig_quit_requested)
            container.sig_restart_requested.connect(self.sig_restart_requested)
            container.sig_redirect_stdio_requested.connect(
                self.sig_redirect_stdio_requested)
            container.sig_exception_occurred.connect(
                self.sig_exception_occurred)
            container.sig_unmaximize_plugin_requested.connect(
                self.sig_unmaximize_plugin_requested)

            self.after_container_creation()

        # Load the custom images of the plugin
        if self.IMG_PATH:
            plugin_path = osp.join(self.get_path(), self.IMG_PATH)
            IMAGE_PATH_MANAGER.add_image_path(plugin_path)

    # ---- Private methods
    # -------------------------------------------------------------------------
    def _register(self, omit_conf=False):
        """
        Setup and register plugin in Spyder's main window and connect it to
        other plugins.
        """
        # Checks
        # --------------------------------------------------------------------
        if self.NAME is None:
            raise SpyderAPIError('A Spyder Plugin must define a `NAME`!')

        # Setup configuration
        # --------------------------------------------------------------------
        if self._conf is not None and not omit_conf:
            self._conf.register_plugin(self)

        # Signals
        # --------------------------------------------------------------------
        self.is_registered = True

        self.update_font()

    def _unregister(self):
        """
        Disconnect signals and clean up the plugin to be able to stop it while
        Spyder is running.
        """

        if self._conf is not None:
            self._conf.unregister_plugin(self)

        self._container = None
        self.is_compatible = None
        self.is_registered = False

    # ---- API: available methods
    # -------------------------------------------------------------------------
    def get_path(self):
        """
        Return the plugin's system path.
        """
        return self._plugin_path

    def get_container(self):
        """
        Return the plugin main container.
        """
        return self._container

    def get_configuration(self):
        """
        Return the Spyder configuration object.
        """
        return self._conf

    def get_main(self):
        """
        Return the Spyder main window..
        """
        return self._main

    def get_plugin(self, plugin_name, error=True) -> SpyderPluginV2:
        """
        Get a plugin instance by providing its name.

        Parameters
        ----------
        plugin_name: str
            Name of the plugin from which its instance will be returned.
        error: bool
            Whether to raise errors when trying to return the plugin's
            instance.
        """
        # Ensure that this plugin has the plugin corresponding to
        # `plugin_name` listed as required or optional.
        requires = set(self.REQUIRES or [])
        optional = set(self.OPTIONAL or [])
        full_set = requires | optional

        if plugin_name in full_set or Plugins.All in full_set:
            try:
                return self._main.get_plugin(plugin_name, error=error)
            except SpyderAPIError as e:
                if plugin_name in optional:
                    return None
                else:
                    raise e
        else:
            raise SpyderAPIError(
                'Plugin "{}" not part of REQUIRES or '
                'OPTIONAL requirements!'.format(plugin_name)
            )

    def is_plugin_enabled(self, plugin_name):
        """Determine if a given plugin is going to be loaded."""
        return self._main.is_plugin_enabled(plugin_name)

    def is_plugin_available(self, plugin_name):
        """Determine if a given plugin is available."""
        return self._main.is_plugin_available(plugin_name)

    def get_dockable_plugins(self):
        """
        Return a list of the required plugin instances.

        Only required plugins that extend SpyderDockablePlugin are returned.
        """
        requires = set(self.REQUIRES or [])
        dockable_plugins_required = []
        for name, plugin_instance in self._main.get_dockable_plugins():
            if (name in requires or Plugins.All in requires) and isinstance(
                    plugin_instance,
                    (SpyderDockablePlugin, SpyderPluginWidget)):
                dockable_plugins_required.append(plugin_instance)
        return dockable_plugins_required

    def get_conf(self, option, default=NoDefault, section=None, secure=False):
        """
        Get an option from Spyder configuration system.

        Parameters
        ----------
        option: str
            Name of the option to get its value from.
        default: bool, int, str, tuple, list, dict, NoDefault
            Value to get from the configuration system, passed as a
            Python object.
        section: str
            Section in the configuration system, e.g. `shortcuts`.
        secure: bool
            If True, the option will be retrieved securely using the `keyring`
            Python package.

        Returns
        -------
        bool, int, str, tuple, list, dict
            Value associated with `option`.
        """
        if self._conf is not None:
            section = self.CONF_SECTION if section is None else section
            if section is None:
                raise SpyderAPIError(
                    'A spyder plugin must define a `CONF_SECTION` class '
                    'attribute!'
                )
            return self._conf.get(section, option, default, secure=secure)

    @Slot(str, object)
    @Slot(str, object, str)
    def set_conf(
        self,
        option,
        value,
        section=None,
        recursive_notification=True,
        secure=False,
    ):
        """
        Set an option in Spyder configuration system.

        Parameters
        ----------
        option: str
            Name of the option (e.g. 'case_sensitive')
        value: bool, int, str, tuple, list, dict
            Value to save in the configuration system, passed as a
            Python object.
        section: str
            Section in the configuration system, e.g. `shortcuts`.
        recursive_notification: bool
            If True, all objects that observe all changes on the
            configuration section and objects that observe partial tuple paths
            are notified. For example if the option `opt` of section `sec`
            changes, then the observers for section `sec` are notified.
            Likewise, if the option `(a, b, c)` changes, then observers for
            `(a, b, c)`, `(a, b)` and a are notified as well.
        secure: bool
            If True, the option will be saved securely using the `keyring`
            Python package.
        """
        if self._conf is not None:
            section = self.CONF_SECTION if section is None else section
            if section is None:
                raise SpyderAPIError(
                    'A spyder plugin must define a `CONF_SECTION` class '
                    'attribute!'
                )

            self._conf.set(
                section,
                option,
                value,
                recursive_notification=recursive_notification,
                secure=secure,
            )
            self.apply_conf({option}, False)

    def remove_conf(self, option, section=None, secure=False):
        """
        Delete an option in the Spyder configuration system.

        Parameters
        ----------
        option: Union[str, Tuple[str, ...]]
            Name of the option, either a string or a tuple of strings.
        section: str
            Section in the configuration system.
        secure: bool
            If True, the option will be removed securely using the `keyring`
            Python package.
        """
        if self._conf is not None:
            section = self.CONF_SECTION if section is None else section
            if section is None:
                raise SpyderAPIError(
                    'A spyder plugin must define a `CONF_SECTION` class '
                    'attribute!'
                )

            self._conf.remove_option(section, option, secure=secure)
            self.apply_conf({option}, False)

    def apply_conf(self, options_set, notify=True):
        """
        Apply `options_set` to this plugin's widget.
        """
        if self._conf is not None and options_set:
            if notify:
                self.after_configuration_update(list(options_set))

    def disable_conf(self, option, section=None):
        """
        Disable notifications for an option in the Spyder configuration system.

        Parameters
        ----------
        option: Union[str, Tuple[str, ...]]
            Name of the option, either a string or a tuple of strings.
        section: str
            Section in the configuration system.
        """
        if self._conf is not None:
            section = self.CONF_SECTION if section is None else section
            if section is None:
                raise SpyderAPIError(
                    'A spyder plugin must define a `CONF_SECTION` class '
                    'attribute!'
                )
            self._conf.disable_notifications(section, option)

    def restore_conf(self, option, section=None):
        """
        Restore notifications for an option in the Spyder configuration system.

        Parameters
        ----------
        option: Union[str, Tuple[str, ...]]
            Name of the option, either a string or a tuple of strings.
        section: str
            Section in the configuration system.
        """
        if self._conf is not None:
            section = self.CONF_SECTION if section is None else section
            if section is None:
                raise SpyderAPIError(
                    'A spyder plugin must define a `CONF_SECTION` class '
                    'attribute!'
                )
            self._conf.restore_notifications(section, option)

    @Slot(str)
    @Slot(str, int)
    def show_status_message(self, message, timeout=0):
        """
        Show message in status bar.

        Parameters
        ----------
        message: str
            Message to display in the status bar.
        timeout: int
            Amount of time to display the message.
        """
        self.sig_status_message_requested.emit(message, timeout)

    def before_long_process(self, message):
        """
        Show a message in main window's status bar and change the mouse
        pointer to Qt.WaitCursor when starting a long process.

        Parameters
        ----------
        message: str
            Message to show in the status bar when the long process starts.
        """
        if message:
            self.show_status_message(message)

        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
        QApplication.processEvents()

    def after_long_process(self, message=""):
        """
        Clear main window's status bar after a long process and restore
        mouse pointer to the OS deault.

        Parameters
        ----------
        message: str
            Message to show in the status bar when the long process finishes.
        """
        QApplication.restoreOverrideCursor()
        self.show_status_message(message, timeout=2000)
        QApplication.processEvents()

    def get_color_scheme(self):
        """
        Get the current color scheme.

        Returns
        -------
        dict
            Dictionary with properties and colors of the color scheme
            used in the Editor.

        Notes
        -----
        This is useful to set the color scheme of all instances of
        CodeEditor used by the plugin.
        """
        if self._conf is not None:
            return get_color_scheme(self._conf.get('appearance', 'selected'))

    def initialize(self):
        """
        Initialize a plugin instance.

        Notes
        -----
        This method should be called to initialize the plugin, but it should
        not be overridden, since it internally calls `on_initialize` and emits
        the `sig_plugin_ready` signal.
        """
        self.on_initialize()
        self.sig_plugin_ready.emit()

    @staticmethod
    def create_icon(name):
        """
        Provide icons from the theme and icon manager.
        """
        return ima.icon(name)

    @classmethod
    def get_font(cls, font_type):
        """
        Return one of font types used in Spyder.

        Parameters
        ----------
        font_type: str
            There are three types of font types in Spyder:
            SpyderFontType.Monospace, used in the Editor, IPython console,
            and History; SpyderFontType.Interface, used by the entire Spyder
            app; and SpyderFontType.MonospaceInterface, used by the Variable
            Explorer, Find, Debugger and others.

        Returns
        -------
        QFont
            QFont object to be passed to other Qt widgets.

        Notes
        -----
        All plugins in Spyder use the same, global fonts. In case some a plugin
        wants to use a delta font size based on the default one, they can set
        the MONOSPACE_FONT_SIZE_DELTA or INTERFACE_FONT_SIZE_DELTA class
        constants.
        """
        if font_type == SpyderFontType.Monospace:
            font_size_delta = cls.MONOSPACE_FONT_SIZE_DELTA
        elif font_type in [SpyderFontType.Interface,
                           SpyderFontType.MonospaceInterface]:
            font_size_delta = cls.INTERFACE_FONT_SIZE_DELTA
        else:
            raise SpyderAPIError("Unrecognized font type")

        return get_font(option=font_type, font_size_delta=font_size_delta)

    def get_command_line_options(self):
        """
        Get command line options passed by the user when they started
        Spyder in a system terminal.

        See app/cli_options.py for the option names.
        """
        if self._main is not None:
            return self._main._cli_options
        else:
            # This is necessary when the plugin has no parent.
            sys_argv = [sys.argv[0]]  # Avoid options passed to pytest
            return get_options(sys_argv)[0]

    # ---- API: Mandatory methods to define
    # -------------------------------------------------------------------------
    @staticmethod
    def get_name():
        """
        Return the plugin localized name.

        Returns
        -------
        str
            Localized name of the plugin.

        Notes
        -----
        This method needs to be decorated with `staticmethod`.
        """
        raise NotImplementedError('A plugin name must be defined!')

    @staticmethod
    def get_description():
        """
        Return the plugin localized description.

        Returns
        -------
        str
            Localized description of the plugin.

        Notes
        -----
        This method needs to be decorated with `staticmethod`.
        """
        raise NotImplementedError('A plugin description must be defined!')

    @classmethod
    def get_icon(cls):
        """
        Return the plugin associated icon.

        Returns
        -------
        QIcon
            QIcon instance

        Notes
        -----
        This method needs to be decorated with `classmethod` or `staticmethod`.
        """
        raise NotImplementedError('A plugin icon must be defined!')

    def on_initialize(self):
        """
        Setup the plugin.

        Notes
        -----
        All calls performed on this method should not call other plugins.
        """
        if hasattr(self, 'register'):
            raise SpyderAPIError(
                'register was replaced by on_initialize, please check the '
                'Spyder 5.1.0 migration guide to get more information')

        raise NotImplementedError(
            f'The plugin {type(self)} is missing an implementation of '
            'on_initialize')

    # ---- API: Optional methods to override
    # -------------------------------------------------------------------------
    @staticmethod
    def check_compatibility():
        """
        This method can be reimplemented to check compatibility of a plugin
        with the user's current environment.

        Returns
        -------
        (bool, str)
            The first value tells Spyder if the plugin has passed the
            compatibility test defined in this method. The second value
            is a message that must explain users why the plugin was
            found to be incompatible (e.g. 'This plugin does not work
            with PyQt4'). It will be shown at startup in a QMessageBox.
        """
        valid = True
        message = ''  # Note: Remember to use _('') to localize the string
        return valid, message

    def on_first_registration(self):
        """
        Actions to be performed the first time the plugin is started.

        It can also be used to perform actions that are needed only the
        first time this is loaded after installation.

        This method is called after the main window is visible.
        """
        pass

    def before_mainwindow_visible(self):
        """
        Actions to be performed after setup but before the main window's has
        been shown.
        """
        pass

    def on_mainwindow_visible(self):
        """
        Actions to be performed after the main window's has been shown.
        """
        pass

    def on_close(self, cancelable=False):
        """
        Perform actions before the plugin is closed.

        This method **must** only operate on local attributes and not other
        plugins.
        """
        if hasattr(self, 'unregister'):
            warnings.warn('The unregister method was deprecated and it '
                          'was replaced by `on_close`. Please see the '
                          'Spyder 5.2.0 migration guide to get more '
                          'information.')

    def can_close(self) -> bool:
        """
        Determine if a plugin can be closed.

        Returns
        -------
        close: bool
            True if the plugin can be closed, False otherwise.
        """
        return True

    def update_font(self):
        """
        This must be reimplemented by plugins that need to adjust their fonts.

        The following plugins illustrate the usage of this method:
          * spyder/plugins/help/plugin.py
          * spyder/plugins/onlinehelp/plugin.py
        """
        pass

    def update_style(self):
        """
        This must be reimplemented by plugins that need to adjust their style.

        Changing from the dark to the light interface theme might
        require specific styles or stylesheets to be applied. When
        the theme is changed by the user through our Preferences,
        this method will be called for all plugins.
        """
        pass

    def after_container_creation(self):
        """
        Perform necessary operations before setting up the container.

        This must be reimplemented by plugins whose containers emit signals in
        on_option_update that need to be connected before applying those
        options to our config system.
        """
        pass

    def after_configuration_update(self, options: List[Union[str, tuple]]):
        """
        Perform additional operations after updating the plugin configuration
        values.

        This can be implemented by plugins that do not have a container and
        need to act on configuration updates.

        Parameters
        ----------
        options: List[Union[str, tuple]]
            A list that contains the options that were updated.
        """
        pass


class SpyderDockablePlugin(SpyderPluginV2):
    """
    A Spyder plugin to enhance functionality with a dockable widget.
    """
    # ---- API: Mandatory attributes
    # -------------------------------------------------------------------------
    # This is the main widget of the dockable plugin.
    # It needs to be a subclass of PluginMainWidget.
    WIDGET_CLASS = None

    # ---- API: Optional attributes
    # -------------------------------------------------------------------------
    # Define a list of plugins next to which we want to to tabify this plugin.
    # Example: ['Plugins.Editor']
    TABIFY = []

    # Disable actions in Spyder main menus when the plugin is not visible
    DISABLE_ACTIONS_WHEN_HIDDEN = True

    # Raise and focus on switch to plugin calls.
    # If False, the widget will be raised but focus will not be given until
    # the action to switch is called a second time.
    RAISE_AND_FOCUS = False

    # Whether the plugin can handle file actions.
    # If set to true, then the `create_new_file`, `open_last_closed_file`,
    # `save_file`, `save_file_as`, `save_copy_as`, `save_all`, `revert_file`,
    # `close_file` and `close_all` functions will be called to handle the
    # corresponding actions. Individual actions can be disabled with
    # `enable_file_action` in the Applications plugin.
    CAN_HANDLE_FILE_ACTIONS = False

    # List of file extensions which the plugin can open.
    # If the user opens a file with one of these extensions, then the file
    # will open in this plugin using the `open_file` function.
    # Example: ['.ipynb'] for spyder-notebook
    FILE_EXTENSIONS = []

    # Whether the plugin can handle edit actions.
    # If set to True, then the `undo`, `redo`, `cut`, `copy`, `paste` and
    # `select_all` functions will be called to handle the corresponding
    # actions. Individual actions can be disabled with `enable_edit_action` in
    # the Applications plugin.
    CAN_HANDLE_EDIT_ACTIONS = False

    # ---- API: Available signals
    # -------------------------------------------------------------------------
    sig_focus_changed = Signal()
    """
    This signal is emitted to inform the focus of this plugin has changed.
    """

    sig_toggle_view_changed = Signal(bool)
    """
    This action is emitted to inform the visibility of a dockable plugin
    has changed.

    This is triggered by checking/unchecking the entry for a pane in the
    `Window > Panes` menu.

    Parameters
    ----------
    visible: bool
        New visibility of the dockwidget.
    """

    sig_switch_to_plugin_requested = Signal(object, bool)
    """
    This signal can be emitted to inform the main window that this plugin
    requested to be displayed.

    Notes
    -----
    This is automatically connected to main container/widget at plugin's
    registration.
    """

    sig_update_ancestor_requested = Signal()
    """
    This signal is emitted to inform the main window that a child widget
    needs its ancestor to be updated.
    """

    # ---- Private methods
    # -------------------------------------------------------------------------
    def __init__(self, parent, configuration):
        if not issubclass(self.WIDGET_CLASS, PluginMainWidget):
            raise SpyderAPIError(
                'A SpyderDockablePlugin must define a valid WIDGET_CLASS '
                'attribute!')

        self.CONTAINER_CLASS = self.WIDGET_CLASS
        super().__init__(parent, configuration=configuration)

        # Shortcut to switch to the plugin. It's defined on the main window
        self._switch_to_shortcut = None

        # Widget setup
        # --------------------------------------------------------------------
        self._widget = self._container
        widget = self._widget
        if widget is None:
            raise SpyderAPIError(
                'A dockable plugin must define a WIDGET_CLASS!')

        if not isinstance(widget, PluginMainWidget):
            raise SpyderAPIError(
                'The WIDGET_CLASS of a dockable plugin must be a subclass of '
                'PluginMainWidget!')

        widget.DISABLE_ACTIONS_WHEN_HIDDEN = self.DISABLE_ACTIONS_WHEN_HIDDEN
        widget.RAISE_AND_FOCUS = self.RAISE_AND_FOCUS
        widget.set_icon(self.get_icon())
        widget.set_name(self.NAME)

        # Render all toolbars as a final separate step on the main window
        # in case some plugins want to extend a toolbar. Since the rendering
        # can only be done once!
        widget.render_toolbars()

        # Default Signals
        # --------------------------------------------------------------------
        widget.sig_toggle_view_changed.connect(self.sig_toggle_view_changed)
        widget.sig_update_ancestor_requested.connect(
            self.sig_update_ancestor_requested)

    # ---- API: Optional methods to override
    # -------------------------------------------------------------------------
    def create_new_file(self) -> None:
        """
        Create a new file inside the plugin.

        This function will be called if the user creates a new file using
        the `File > New` menu item or the "New file" button in the main
        toolbar, and `CAN_HANDLE_FILE_ACTIONS` is set to `True`.
        """
        raise NotImplementedError

    def open_file(self, filename: str):
        """
        Open file inside plugin.

        This method will be called if the user wants to open a file with one
        of the file name extensions listed in `FILE_EXTENSIONS`, so you need
        to define that variable too.

        Parameters
        ----------
        filename: str
            The name of the file to be opened.
        """
        raise NotImplementedError

    def get_current_filename(self) -> Optional[str]:
        """
        Return file name of the file that is currently displayed.

        This is meant for plugins like the Editor or Notebook plugin which
        can edit or display files. Return `None` if no file is displayed or if
        this does not display files.

        This function is used in the `Open file` action to initialize the
        "Open file" dialog.
        """
        return None

    def current_file_is_temporary(self) -> bool:
        """
        Return whether the currently displayed file is a temporary file.

        This function should only be called if a file is displayed, that is,
        if `self.get_current_filename()` does not return `None`.
        """
        return False

    def open_last_closed_file(self) -> None:
        """
        Open the last closed file again.

        This function will be called if the `File > Open last closed` menu item
        is selected while the plugin has focus and `CAN_HANDLE_FILE_ACTIONS`
        is set to `True`.
        """
        raise NotImplementedError

    def save_file(self) -> None:
        """
        Save the current file.

        This function will be called if the user saves the current file using
        the `File > Save` menu item or the "Save file" button in the main
        toolbar, the plugin has focus, and `CAN_HANDLE_FILE_ACTIONS` is set to
        `True`.
        """
        raise NotImplementedError

    def save_file_as(self) -> None:
        """
        Save the current file under a different name.

        This function will be called if the `File > Save as` menu item is
        selected while the plugin has focus and `CAN_HANDLE_FILE_ACTIONS` is
        set to `True`.
        """
        raise NotImplementedError

    def save_copy_as(self) -> None:
        """
        Save a copy of the current file under a different name.

        This function will be called if the `File > Save copy as` menu item is
        selected while the plugin has focus and `CAN_HANDLE_FILE_ACTIONS` is
        set to `True`.
        """
        raise NotImplementedError

    def save_all(self) -> None:
        """
        Save all files that are opened in the plugin.

        This function will be called if the user saves all files using the
        `File > Save all` menu item or the "Save all" button in the main
        toolbar, the plugin has focus, and `CAN_HANDLE_FILE_ACTIONS` is set to
        `True`.
        """
        raise NotImplementedError

    def revert_file(self) -> None:
        """
        Revert the current file to the version stored on disk.

        This function will be called if the `File > Revert` menu item is
        selected while the plugin has focus and `CAN_HANDLE_FILE_ACTIONS` is
        set to `True`.
        """
        raise NotImplementedError

    def close_file(self) -> None:
        """
        Close the current file.

        This function will be called if the `File > Close` menu item is
        selected while the plugin has focus and `CAN_HANDLE_FILE_ACTIONS` is
        set to `True`.
        """
        raise NotImplementedError

    def close_all(self) -> None:
        """
        Close all opened files.

        This function will be called if the `File > Close all` menu item is
        selected while the plugin has focus and `CAN_HANDLE_FILE_ACTIONS` is
        set to `True`.
        """
        raise NotImplementedError

    def undo(self) -> None:
        """
        Undo last edition.

        This function will be called if the `Edit > Undo` menu item is
        selected while the plugin has focus and `CAN_HANDLE_EDIT_ACTIONS` is
        set to `True`.
        """
        raise NotImplementedError

    def redo(self) -> None:
        """
        Redo last edition.

        This function will be called if the `Edit > Redo` menu item is
        selected while the plugin has focus and `CAN_HANDLE_EDIT_ACTIONS` is
        set to `True`.
        """
        raise NotImplementedError

    def cut(self) -> None:
        """
        Cut selection.

        This function will be called if the `Edit > Cut` menu item is
        selected while the plugin has focus and `CAN_HANDLE_EDIT_ACTIONS` is
        set to `True`.
        """
        raise NotImplementedError

    def copy(self) -> None:
        """
        Copy selection.

        This function will be called if the `Edit > Copy` menu item is
        selected while the plugin has focus and `CAN_HANDLE_EDIT_ACTIONS` is
        set to `True`.
        """
        raise NotImplementedError

    def paste(self) -> None:
        """
        Paste clipboard.

        This function will be called if the `Edit > Paste` menu item is
        selected while the plugin has focus and `CAN_HANDLE_EDIT_ACTIONS` is
        set to `True`.
        """
        raise NotImplementedError

    def select_all(self) -> None:
        """
        Select all text in the plugin.

        This function will be called if the `Edit > Select All` menu item is
        selected while the plugin has focus and `CAN_HANDLE_EDIT_ACTIONS` is
        set to `True`.
        """
        raise NotImplementedError

    # ---- API: available methods
    # -------------------------------------------------------------------------
    def before_long_process(self, message):
        """
        Show a message in main window's status bar, change the mouse pointer
        to Qt.WaitCursor and start spinner when starting a long process.

        Parameters
        ----------
        message: str
            Message to show in the status bar when the long process starts.
        """
        self.get_widget().start_spinner()
        super().before_long_process(message)

    def after_long_process(self, message=""):
        """
        Clear main window's status bar after a long process, restore mouse
        pointer to the OS deault and stop spinner.

        Parameters
        ----------
        message: str
            Message to show in the status bar when the long process finishes.
        """
        super().after_long_process(message)
        self.get_widget().stop_spinner()

    def get_widget(self) -> PluginMainWidget:
        """
        Return the plugin main widget.
        """
        if self._widget is None:
            raise SpyderAPIError('Dockable Plugin must have a WIDGET_CLASS!')

        return self._widget

    def update_title(self):
        """
        Update plugin title, i.e. dockwidget or window title.
        """
        self.get_widget().update_title()

    def update_margins(self, margin):
        """
        Update margins of main widget inside dockable plugin.
        """
        self.get_widget().update_margins(margin)

    @Slot()
    def switch_to_plugin(self, force_focus=False):
        """
        Switch to plugin and define if focus should be given or not.
        """
        if self.get_widget().windowwidget is None:
            self.sig_switch_to_plugin_requested.emit(self, force_focus)

    def set_ancestor(self, ancestor_widget):
        """
        Update the ancestor/parent of child widgets when undocking.
        """
        self.get_widget().set_ancestor(ancestor_widget)

    # ---- Convenience methods from the widget exposed on the plugin
    # -------------------------------------------------------------------------
    @property
    def dockwidget(self):
        return self.get_widget().dockwidget

    @property
    def options_menu(self):
        return self.get_widget().get_options_menu()

    @property
    def toggle_view_action(self):
        return self.get_widget().toggle_view_action

    def create_dockwidget(self, mainwindow):
        return self.get_widget().create_dockwidget(mainwindow)

    def create_window(self):
        self.get_widget().create_window()

    def close_window(self, save_undocked=False):
        self.get_widget()._close_window(save_undocked=save_undocked)

    def change_visibility(self, state, force_focus=False):
        self.get_widget().change_visibility(state, force_focus)

    def toggle_view(self, value):
        self.get_widget().toggle_view(value)
