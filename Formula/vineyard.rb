class Vineyard < Formula
  include Language::Python::Virtualenv

  desc "TUI factory: PRD to multi-stack codebase via Pydantic AI Gateway and Managed Agents"
  homepage "https://github.com/vineyard-dev/vineyard"
  url "https://files.pythonhosted.org/packages/source/v/vineyard/vineyard-0.2.0.tar.gz"
  sha256 "REPLACE_ON_RELEASE"
  license "MIT"

  depends_on "python@3.12"
  depends_on "uv"

  def install
    # uv handles the venv + dependency resolution; brew just shells out.
    system "uv", "tool", "install", "--directory", buildpath, "--target", libexec.to_s, "vineyard"
    (bin/"vineyard").write_env_script libexec/"bin/vineyard", PATH: "#{libexec}/bin:$PATH"
  end

  test do
    assert_match "Vineyard", shell_output("#{bin}/vineyard --help")
  end
end
