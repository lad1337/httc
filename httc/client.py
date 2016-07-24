import logging

import cec


class PowerStatus:

    def __init__(self, power_on):
        self.power_on = power_on

    def __str__(self):
        if self.power_on:
            return 'on'
        return 'standby'

    def __repr__(self):
        return '<Power: %s>' % self

    def __bool__(self):
        return self.power_on


def sanitize_name(name):
    return name.replace(" ", "_").replace("/", "_").replace("(", "").replace(")", "").lower()


BUTTONS = [
    "Select", "Up", "Down", "Left", "Right", "Right-Up", "Right-Down", "Left-Up", "Left-Down", "Root Menu",
    "Setup Menu", "Contents Menu", "Favorite Menu", "Exit", "Reserved 0x0E", "Reserved 0x0F", "Reserved 0x10",
    "Reserved 0x11", "Reserved 0x12", "Reserved 0x13", "Reserved 0x14", "Reserved 0x15", "Reserved 0x16",
    "Reserved 0x17", "Reserved 0x18", "Reserved 0x19", "Reserved 0x1A", "Reserved 0x1B", "Reserved 0x1C",
    "Reserved 0x1D", "Reserved 0x1E", "Reserved 0x1F", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "Dot",
    "Enter", "Clear", "Reserved 0x2D", "Reserved 0x2E", "Next Favorite", "Channel Up", "Channel Down",
    "Previous Channel", "Sound Select", "Input Select", "Display Information", "Help", "Page Up", "Page Down",
    "Reserved 0x39", "Reserved 0x3A", "Reserved 0x3B", "Reserved 0x3C", "Reserved 0x3D", "Reserved 0x3E",
    "Reserved 0x3F", "Power", "Volume Up", "Volume Down", "Mute", "Play", "Stop", "Pause", "Record", "Rewind",
    "Fast Forward", "Eject", "Forward", "Backward", "Stop-Record", "Pause-Record", "Reserved 0x4F", "Angle",
    "Sub Picture", "Video On Demand", "Electronic program Guide", "Timer programming", "Initial Configuration",
    "Reserved 0x56", "Reserved 0x57", "Reserved 0x58", "Reserved 0x59", "Reserved 0x5A", "Reserved 0x5B",
    "Reserved 0x5C", "Reserved 0x5D", "Reserved 0x5E", "Reserved 0x5F", "Play Function", "Pause-Play Function",
    "Record Function", "Pause-Record Function", "Stop Function", "Mute Function", "Restore Volume Function",
    "Tune Function", "Select media Function", "Select A/V Input Function", "Select Audio input Function",
    "Power Toggle Function", "Power Off Function", "Power On Function", "Reserved 0x6E", "Reserved 0x6F",
    "Reserved 0x70", "F1 (Blue)", "F2 (Red)", "F3 (Green)", "F4 (Yellow)", "F5", "Data"
]

BUTTON_CODES = {"{code:x}".format(code=i): name for i, name in enumerate(BUTTONS)}
BUTTON_NAMES = {sanitize_name(name): code for code, name in BUTTON_CODES.items()}


class CECClient:

    def __init__(self, osd_name=None, device_types=None, init=True, key_press_callback=None):
        self.logger = logging.getLogger('CECClient')
        self.logger_bus = logging.getLogger('CECClient.bus')
        self.logger_keypress = logging.getLogger('CECClient.key')

        self.key_press_callback = key_press_callback

        self.cecconfig = cec.libcec_configuration()
        self.cecconfig.strDeviceName = osd_name or "pyCecClient"
        self.cecconfig.bActivateSource = 0
        self.cecconfig.clientVersion = cec.LIBCEC_VERSION_CURRENT

        # FIXME: this does not work at all
        self.cecconfig.SetLogCallback(self.log_callback)
        self.cecconfig.SetKeyPressCallback(self.key_press_callback_proxy)

        if device_types:
            for device_type in device_types:
                self.cecconfig.deviceTypes.Add(device_type)
        else:
            self.cecconfig.deviceTypes.Add(cec.CEC_DEVICE_TYPE_RECORDING_DEVICE)
        self.connection = cec.ICECAdapter.Create(self.cecconfig)
        self.connected = False
        self._logical_address = None
        self._devices = None
        if init:
            self.init()

    def init(self):
        self._logical_address = None
        adapters = self.connection.DetectAdapters()
        if not adapters:
            raise ConnectionError('No CEC Adapters found')
        self.connected = self.connection.Open(adapters[0].strComName)

    def log_callback(self, level, time, message):
        own_log_level = self.logger.getLogLevel()
        print("foo", message)
        log_level_map = {
            cec.CEC_LOG_ERROR: logging.ERROR,
            cec.CEC_LOG_WARNING: logging.WARNING,
            cec.CEC_LOG_NOTICE: logging.INFO,
            cec.CEC_LOG_TRAFFIC: logging.DEBUG,
            cec.CEC_LOG_DEBUG: logging.DEBUG,
        }
        self.logger_bus.log(log_level_map[level], message)

    def key_press_callback_proxy(self, key, duration):
        self.logger_keypress.debug('{} pressed for {}', key, duration)
        if self.key_press_callback is not None:
            self.key_press_callback(key, duration)

    @property
    def logical_address(self):
        if self._logical_address is None:
            self._logical_address = self.connection.GetLogicalAddresses().primary
        return self._logical_address

    @property
    def devices(self):
        if self._devices is None:
            self._devices = self.scan()
        return self._devices

    def raw_command(self, data):
        self.logger.debug('Sending command: %s', data)
        cmd = self.connection.CommandFromString(data)
        return self.connection.Transmit(cmd)

    def scan(self):
        addresses = self.connection.GetActiveDevices()
        # stolen from the libcec but it does not look like its used
        activeSource = self.connection.GetActiveSource()
        x = 0
        devices = {}
        while x < 15:
          if addresses.IsSet(x):
            devices[x] = {
                'vendor_id': self.connection.GetDeviceVendorId(x),
                'physical_address': int(str(self.connection.GetDevicePhysicalAddress(x))),
                'logical_address': x,
                'active': self.connection.IsActiveSource(x),
                'cec_version': self.connection.GetDeviceCecVersion(x),
                'power_status': PowerStatus(self.connection.GetDevicePowerStatus(x) == 0),
                'osd_name': self.connection.GetDeviceOSDName(x)
            }
          x += 1
        self._devices = devices
        return devices

    def button_release(self, dst, src=None):
        src = src or self.logical_address
        return self.raw_command('{src:x}{dst:x}:45'.format(src=src, dst=dst))

    def button_press(self, button, dst, release, src=None):
        src = src or self.logical_address
        result_press = self.raw_command(
            '{src:x}{dst:x}:44:{button}'.format(src=src, dst=dst, button=button))
        result_release = True
        if release:
            result_release = self.button_release(dst)
        return result_press and result_release

    def button_menu(self, dst, release=True):
        return self.button_press("45", dst, release)

    def button_select(self, dst, release=True):
        return self.button_press("44", dst, release)

    def standby(self, src=None, dst=None):
        src = src or self.logical_address
        dst = dst or 0
        return self.raw_command('{src:x}{dst:x}:36'.format(src=src, dst=dst))

    def active_source(self, logical_address=None, physical_address=None):
        if logical_address is None and physical_address is None:
            raise ValueError('no logical_address nor phisical_address given')
        target = physical_address or self.devices[logical_address]['physical_address']
        target = '{:04x}'.format(target)
        target = target[0:1] + ':' + target[2:3]
        return self.raw_command('{src}F:82:{target}'.format(src=self.logical_address, target=target))

    def power_status(self, dst):
        return PowerStatus(self.connection.GetDevicePowerStatus(dst) == 0)