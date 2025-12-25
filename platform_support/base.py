"""
WhisperRocket - Platform Handler Base Class
Abstract base class a platform-specifikus műveletekhez
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional


class PlatformHandler(ABC):
    """Platform-specifikus műveletek abstract base class"""

    @abstractmethod
    def get_config_dir(self) -> Path:
        """Config mappa platform-specifikus útvonala"""
        pass

    @abstractmethod
    def get_cache_dir(self) -> Path:
        """Cache mappa (HuggingFace modellek) platform-specifikus útvonala"""
        pass

    @abstractmethod
    def paste_text(self, is_terminal: bool = False) -> None:
        """Szöveg beillesztése az aktív ablakba

        Args:
            is_terminal: True ha terminál ablakba kell beilleszteni
        """
        pass

    @abstractmethod
    def play_sound(self, path: str) -> None:
        """Hang lejátszása

        Args:
            path: Hangfájl útvonala
        """
        pass

    @abstractmethod
    def get_active_window_class(self) -> str:
        """Aktív ablak class nevének lekérdezése

        Returns:
            Ablak class neve (pl. "gnome-terminal", "Terminal")
        """
        pass

    @abstractmethod
    def is_terminal_window(self, window_class: str) -> bool:
        """Ellenőrzi, hogy az ablak terminál-e

        Args:
            window_class: Ablak class neve

        Returns:
            True ha terminál ablak
        """
        pass

    @abstractmethod
    def setup_autostart(self, enable: bool, app_path: Optional[str] = None) -> bool:
        """Autostart be/kikapcsolása

        Args:
            enable: True = bekapcsolás, False = kikapcsolás
            app_path: Alkalmazás útvonala (opcionális)

        Returns:
            True ha sikeres
        """
        pass

    @abstractmethod
    def is_autostart_enabled(self) -> bool:
        """Ellenőrzi, hogy az autostart be van-e kapcsolva

        Returns:
            True ha be van kapcsolva
        """
        pass

    @abstractmethod
    def check_permissions(self) -> dict:
        """Szükséges engedélyek ellenőrzése

        Returns:
            Dict az engedélyekkel: {"microphone": bool, "accessibility": bool}
        """
        pass

    @abstractmethod
    def request_permissions(self) -> None:
        """Engedélyek kérése (UI megnyitása ha szükséges)"""
        pass

    @abstractmethod
    def has_gpu_support(self) -> bool:
        """Ellenőrzi, hogy van-e GPU támogatás

        Returns:
            True ha van GPU (CUDA vagy MLX)
        """
        pass

    @abstractmethod
    def get_gpu_type(self) -> str:
        """GPU típus lekérdezése

        Returns:
            "cuda", "mlx", vagy "cpu"
        """
        pass

    @abstractmethod
    def kill_app(self, process_name: str) -> None:
        """Alkalmazás leállítása

        Args:
            process_name: Process neve
        """
        pass

    @abstractmethod
    def restart_app(self, start_script: str) -> None:
        """Alkalmazás újraindítása

        Args:
            start_script: Indító script útvonala
        """
        pass
