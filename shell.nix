{ pkgs ? import <nixpkgs> { } }:

pkgs.mkShell {
  buildInputs = [
    # The command line utility for PT-series printers
    pkgs.ptouch-print

    # Python environment with required libraries
    (pkgs.python3.withPackages (ps: with ps; [ qrcode pillow ]))

    # Required for USB communication
    pkgs.libusb1
    pkgs.pkg-config
  ];

  shellHook = "python qr.py --help";
}
