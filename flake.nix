{
  inputs = {
    nixpkgs.url = "nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, flake-utils, nixpkgs, ... }:
    flake-utils.lib.eachDefaultSystem (system: let pkgs = import nixpkgs {
        inherit system;
        config.allowUnfree = true;
    }; in {
      devShells.default = pkgs.mkShell {
        version = "0.1.0";
        buildInputs = with pkgs; [
            rye
            steam-run
        ];

        # This is _disgusting_, but we alias "rye" to "steam-run rye" because... NixOS
        shellHook = ''
          alias rye="steam-run rye"
        '';
      };
    });
}