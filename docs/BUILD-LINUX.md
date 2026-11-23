# Building Linux packages (.deb / .rpm) for Shakshuka

Shakshuka ships as a **self-contained** package: the project source lives under
`/opt/shakshuka/` together with a vendored Python venv (dependencies installed
at build time), a launcher script, and a desktop menu entry.

> Note: the old `fpm -s python setup.py` packaging is gone. It installed Python
> modules into site-packages without the app's runtime assets, which crashed on
> launch (`jinja2.exceptions.TemplateNotFound: index.html`, missing
> `config/version.json`). The new layout avoids that entirely.

## Prerequisites

These steps must run **on Linux** (Debian/Ubuntu or Fedora/RHEL). On other
platforms, use the GitHub Actions `release.yml` workflow instead.

1. **Build tools + fpm:**
   ```bash
   sudo apt-get update
   sudo apt-get install ruby ruby-dev build-essential python3-venv
   sudo gem install fpm
   ```
2. **For .rpm additionally:**
   ```bash
   sudo apt-get install rpm rpm-build      # Debian/Ubuntu
   # sudo dnf install rpm-build            # Fedora/RHEL/openSUSE
   ```

No separate `pip install -r` needed — the builder creates the venv and installs
`config/requirements-linux.txt` into the package itself.

## Building

```bash
# .deb (Debian/Ubuntu)
python3 scripts/build-deb.py        # or: ./scripts/build-deb.sh

# .rpm (Fedora/RHEL/openSUSE)
python3 scripts/build-rpm.py        # or: ./scripts/build-rpm.sh

# both at once
python3 scripts/build_linux_pkg.py both
```

## Output

- `dist/shakshuka_<version>_amd64.deb`
- `dist/shakshuka-<version>-1.x86_64.rpm`

## Installing

```bash
# Debian/Ubuntu
sudo dpkg -i dist/shakshuka_<version>_amd64.deb

# Fedora/RHEL/openSUSE
sudo dnf install dist/shakshuka-<version>-1.x86_64.rpm
```

Then launch with `shakshuka` (terminal starter) or from your app menu.
User data goes to `~/.shakshuka/` in every case.

## Notes

- The venv is built on the build machine — the package targets the given
  architecture/glibc (CI builds: `ubuntu-latest` x86_64 wheels).
- System tray requires a desktop environment with AppIndicator
  (`sudo apt install gir1.2-ayatanaappindicator3-0.1` on modern Ubuntu).
  Under WSL there is no tray/notification area, which is expected.

## Uninstalling

```bash
sudo apt-get remove shakshuka        # Debian/Ubuntu
sudo dnf remove shakshuka            # Fedora/RHEL/openSUSE
```

Removing the package also removes the `/usr/bin/shakshuka` symlink
(see `scripts/pkgscripts/prerm.sh`). User data at `~/.shakshuka/` is kept.

## Troubleshooting

### Missing templates / `version.json` after install
You have an old `fpm -s python` build installed. Remove it and reinstall the
self-contained package:
```bash
sudo apt-get remove --purge shakshuka && sudo dpkg -i dist/shakshuka_*_amd64.deb
```

### fpm not found
- Make sure fpm is installed: `gem list fpm`
- Check PATH: `which fpm`

### RPM build fails with "rpmbuild not found"
- Install it: `sudo apt install rpm rpm-build` (host building for RPM)

## Files Created

- `scripts/build_linux_pkg.py` - Generic self-contained .deb/.rpm builder
- `scripts/build-deb.py` / `scripts/build-rpm.py` - thin wrappers
- `scripts/build-deb.sh` / `scripts/build-rpm.sh` - bash wrappers
- `config/requirements-linux.txt` - Linux dependencies (vendored into the package)

## Version Management

The version is automatically read from `config/version.json`. To change the version, update the `version` field in that file.

