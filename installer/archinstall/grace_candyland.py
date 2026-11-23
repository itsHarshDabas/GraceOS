"""Grace Candyland as an archinstall desktop profile, for installing it from Arch's own ISO.

archinstall loads this file through the "path" in grace-candyland.json (see README.md here).
It adds one desktop to archinstall's Desktop menu, "Grace Candyland", which installs the
grace-candyland-desktop package from the GraceOS repo (the JSON adds that repo) and SDDM,
whose session list then offers Grace Candyland.
"""

from typing import override

from archinstall.default_profiles.profile import DisplayServerType, GreeterType, Profile, ProfileType


class GraceCandylandProfile(Profile):
	def __init__(self) -> None:
		super().__init__(
			'Grace Candyland',
			ProfileType.DesktopEnv,
			support_gfx_driver=True,
			display_server=DisplayServerType.Wayland,
		)

	@property
	@override
	def packages(self) -> list[str]:
		# grace-candyland-desktop pulls in the shell, the apps, Ollama and the Settings back ends.
		return ['grace-candyland-desktop', 'polkit', 'qt6-wayland']

	@property
	@override
	def services(self) -> list[str]:
		# NetworkManager comes from the network choice; Bluetooth backs the Settings page and bar toggle.
		return ['bluetooth']

	@property
	@override
	def default_greeter_type(self) -> GreeterType:
		return GreeterType.Sddm
