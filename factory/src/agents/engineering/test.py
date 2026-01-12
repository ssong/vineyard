"""Test Agent - RSpec test generation for Rails."""

from typing import Any

from src.agents.base import BaseAgent
from src.config.prompts import TEST_AGENT_PROMPT
from src.models import FactoryState, GeneratedFile
from src.tools import github, llm
from src.tools.generation_context import GenerationContext


class TestAgent(BaseAgent):
    """Agent for generating RSpec tests for Rails."""

    name = "TestAgent"
    domain = "engineering"

    def run(self, state: FactoryState) -> dict[str, Any]:
        """
        Generate RSpec unit, request, and system tests.

        Uses GenerationContext to:
        1. Build context from existing source files
        2. Track generated test files to prevent duplicates
        3. Ensure tests match actual source file structure
        """
        self.log_start()

        opp = state.handoff.opportunity
        prefs = state.handoff.build_preferences
        spec = self.get_previous_output(state, "spec")
        build = self.get_previous_output(state, "build")

        # Initialize context with existing source files from build phase
        ctx = GenerationContext()
        code_output = build.get("code", {}) if isinstance(build, dict) else {}
        source_files = code_output.get("files", []) if code_output else []

        # Add source files to context for reference
        for f in source_files:
            exports = ctx.extract_exports_from_ruby(f.content)
            category = self._categorize_source_file(f.path)
            ctx.add_file(f.path, f.content, f.language, category, exports=exports)

        self.logger.info(f"Building tests for {len(source_files)} source files")

        # Generate test configuration first
        self._generate_test_config(ctx, prefs)

        # Generate test factories (FactoryBot)
        self._generate_factories(ctx, spec, source_files)

        # Generate model specs
        self._generate_model_specs(ctx, source_files, prefs)

        # Generate request specs (API/controller tests)
        self._generate_request_specs(ctx, spec, prefs)

        # Generate system specs (E2E with Capybara)
        self._generate_system_specs(ctx, opp, prefs)

        # Get only test files (not source files)
        test_files = [
            GeneratedFile(path=e.path, content=e.content, language=e.language)
            for e in ctx.get_all_files()
            if e.category in ["test", "test_config", "factory", "support"]
        ]

        self.logger.info(f"Generated {len(test_files)} test files")

        # Push to GitHub
        self._push_tests_to_github(state, test_files)

        # Count by type
        model_count = len([f for f in test_files if "models" in f.path])
        request_count = len([f for f in test_files if "requests" in f.path])
        system_count = len([f for f in test_files if "system" in f.path])

        output = {
            "test_files": test_files,
            "model_spec_count": model_count,
            "request_spec_count": request_count,
            "system_spec_count": system_count,
        }

        self.log_complete()
        return output

    def _categorize_source_file(self, path: str) -> str:
        """Categorize a source file for context tracking."""
        if "controllers/api" in path:
            return "api"
        elif "controllers" in path:
            return "controller"
        elif "models" in path:
            return "model"
        elif "services" in path:
            return "service"
        elif "components" in path:
            return "component"
        elif "views" in path:
            return "view"
        elif "jobs" in path:
            return "job"
        elif "mailers" in path:
            return "mailer"
        else:
            return "source"

    def _generate_test_config(self, ctx: GenerationContext, prefs) -> None:
        """Generate RSpec configuration files."""
        user_prompt = f"""Generate RSpec configuration files for a Rails 7.1 project.

## Requirements

Generate JSON with configuration files:
{{
    "files": [
        {{
            "path": "spec/spec_helper.rb",
            "language": "ruby",
            "content": "# RSpec configuration"
        }},
        {{
            "path": "spec/rails_helper.rb",
            "language": "ruby",
            "content": "# Rails test configuration"
        }}
    ]
}}

Generate:
1. spec/spec_helper.rb - Core RSpec configuration
   - Configure RSpec with recommended settings
   - Random test ordering
   - Filter run with focus
   - Disable monkey patching

2. spec/rails_helper.rb - Rails-specific test setup
   - Require spec_helper
   - Require Rails environment
   - Configure database cleaner strategy
   - Include FactoryBot methods
   - Include Devise test helpers
   - Include Capybara for system tests
   - Configure Shoulda Matchers

3. spec/support/factory_bot.rb - FactoryBot configuration
   - Include FactoryBot::Syntax::Methods

4. spec/support/devise.rb - Devise test helpers
   - Include Devise::Test::IntegrationHelpers for request specs
   - Include Devise::Test::ControllerHelpers for controller specs

5. spec/support/capybara.rb - Capybara configuration
   - Configure Selenium with headless Chrome
   - Set default wait time
   - Configure screenshot on failure

6. spec/support/vcr.rb - VCR for external API mocking
   - Configure cassette library
   - Filter sensitive data
"""

        try:
            result = llm.generate_json(TEST_AGENT_PROMPT, user_prompt)

            for f in result.get("files", []):
                ctx.add_file(
                    f.get("path", "spec/spec_helper.rb"),
                    f.get("content", ""),
                    f.get("language", "ruby"),
                    "test_config",
                )

        except Exception as e:
            self.logger.error(f"Failed to generate test config: {e}")

    def _generate_model_specs(
        self, ctx: GenerationContext, source_files: list, prefs
    ) -> None:
        """Generate model specs."""
        # Get model files
        model_files = ctx.get_files_by_category("model")

        # Build detailed file info with exports
        files_detail = []
        for entry in model_files:
            exports_str = ", ".join(entry.exports[:5]) if entry.exports else "model class"
            files_detail.append(f"- {entry.path}: defines {{ {exports_str} }}")

        files_text = "\n".join(files_detail[:15])

        user_prompt = f"""Generate RSpec model specs for Rails models.

## Models to Test
{files_text}

## Current Project Structure
{ctx.get_folder_structure()}

## Available Factories
{ctx.get_available_components(category="factory")}

## Requirements

Generate JSON with spec files:
{{
    "files": [
        {{
            "path": "spec/models/user_spec.rb",
            "language": "ruby",
            "content": "# Full spec implementation"
        }}
    ]
}}

For each model, generate a corresponding spec file that:
1. Uses FactoryBot factories (e.g., `create(:user)`, `build(:user)`)
2. Tests validations using Shoulda Matchers
3. Tests associations using Shoulda Matchers
4. Tests scopes
5. Tests instance methods
6. Tests class methods

Spec file naming: spec/models/[model_name]_spec.rb

Example structure:
```ruby
require 'rails_helper'

RSpec.describe User, type: :model do
  describe 'validations' do
    it {{ is_expected.to validate_presence_of(:email) }}
    it {{ is_expected.to validate_uniqueness_of(:email).case_insensitive }}
  end

  describe 'associations' do
    it {{ is_expected.to have_many(:posts).dependent(:destroy) }}
  end

  describe 'scopes' do
    describe '.active' do
      it 'returns only active users' do
        active_user = create(:user, status: 'active')
        inactive_user = create(:user, status: 'inactive')
        expect(described_class.active).to include(active_user)
        expect(described_class.active).not_to include(inactive_user)
      end
    end
  end

  describe '#full_name' do
    it 'returns first and last name' do
      user = build(:user, first_name: 'John', last_name: 'Doe')
      expect(user.full_name).to eq('John Doe')
    end
  end
end
```

{ctx.get_deduplication_instructions()}
"""

        try:
            result = llm.generate_json(TEST_AGENT_PROMPT, user_prompt)

            for f in result.get("files", []):
                path = f.get("path", "spec/models/model_spec.rb")
                content = f.get("content", "")
                ctx.add_file(path, content, f.get("language", "ruby"), "test")

        except Exception as e:
            self.logger.error(f"Failed to generate model specs: {e}")

    def _generate_request_specs(
        self, ctx: GenerationContext, spec, prefs
    ) -> None:
        """Generate request specs for API/controller testing."""
        if not spec or not spec.api_endpoints:
            return

        # Build detailed endpoint info
        endpoints_detail = []
        for e in spec.api_endpoints:
            auth = "Auth required" if e.auth_required else "Public"
            endpoints_detail.append(
                f"- {e.method} {e.path}: {e.description} ({auth})"
            )

        endpoints_text = "\n".join(endpoints_detail)

        # Get controller files for context
        controller_files = ctx.get_files_by_category("controller")
        api_files = ctx.get_files_by_category("api")
        controller_imports = "\n".join([f"- {f.path}" for f in controller_files + api_files])

        user_prompt = f"""Generate RSpec request specs for Rails controllers/API.

## API Endpoints
{endpoints_text}

## Controller Files
{controller_imports}

## Available Factories
{ctx.get_available_components(category="factory")}

## Configuration
- AUTH: {prefs.auth_preference}

## Requirements

Generate JSON with request spec files:
{{
    "files": [
        {{
            "path": "spec/requests/users_spec.rb",
            "language": "ruby",
            "content": "# Full request spec"
        }}
    ]
}}

Each request spec should:
1. Use FactoryBot for test data
2. Test authentication (sign_in helper for Devise)
3. Test happy path responses
4. Test error responses (validation errors, not found, unauthorized)
5. Test JSON response structure for API endpoints
6. Group related endpoints in the same spec file

Example structure:
```ruby
require 'rails_helper'

RSpec.describe 'Users', type: :request do
  let(:user) {{ create(:user) }}

  describe 'GET /api/v1/users' do
    context 'when authenticated' do
      before {{ sign_in user }}

      it 'returns a list of users' do
        create_list(:user, 3)
        get '/api/v1/users'

        expect(response).to have_http_status(:ok)
        expect(json_response['users'].length).to eq(4) # including signed in user
      end
    end

    context 'when not authenticated' do
      it 'returns unauthorized' do
        get '/api/v1/users'
        expect(response).to have_http_status(:unauthorized)
      end
    end
  end

  describe 'POST /api/v1/users' do
    let(:valid_params) {{ {{ user: {{ email: 'test@example.com', password: 'password123' }} }} }}

    it 'creates a new user' do
      expect {{
        post '/api/v1/users', params: valid_params
      }}.to change(User, :count).by(1)

      expect(response).to have_http_status(:created)
    end

    context 'with invalid params' do
      let(:invalid_params) {{ {{ user: {{ email: '' }} }} }}

      it 'returns validation errors' do
        post '/api/v1/users', params: invalid_params
        expect(response).to have_http_status(:unprocessable_entity)
        expect(json_response['errors']).to be_present
      end
    end
  end
end
```

Also generate spec/support/request_helpers.rb with:
- json_response helper method
- Common authentication helpers

{ctx.get_deduplication_instructions()}
"""

        try:
            result = llm.generate_json(TEST_AGENT_PROMPT, user_prompt)

            for f in result.get("files", []):
                path = f.get("path", "spec/requests/request_spec.rb")
                content = f.get("content", "")
                category = "support" if "support" in path else "test"
                ctx.add_file(path, content, f.get("language", "ruby"), category)

        except Exception as e:
            self.logger.error(f"Failed to generate request specs: {e}")

    def _generate_system_specs(self, ctx: GenerationContext, opp, prefs) -> None:
        """Generate system specs using Capybara."""
        # Get view files for coverage context
        view_files = ctx.get_files_by_category("view")
        pages_list = "\n".join([f"- {f.path}" for f in view_files])

        user_prompt = f"""Generate RSpec system specs using Capybara for Rails.

## Product
- NAME: {opp.name}
- DESCRIPTION: {opp.detailed_description}
- BUSINESS MODEL: {opp.business_model}

## Views/Pages to Test
{pages_list if pages_list else "Standard SaaS pages (landing, auth, dashboard)"}

## Requirements

Generate JSON with system spec files:
{{
    "files": [
        {{
            "path": "spec/system/authentication_spec.rb",
            "language": "ruby",
            "content": "# Capybara system spec"
        }}
    ]
}}

Generate system specs for:
1. spec/system/authentication_spec.rb - Sign up and login flows
2. spec/system/dashboard_spec.rb - Main app functionality
3. spec/system/settings_spec.rb - User settings
4. spec/system/navigation_spec.rb - Site navigation

Each system spec should:
- Use Capybara DSL (visit, fill_in, click_button, etc.)
- Use FactoryBot for test data
- Test complete user workflows
- Handle JavaScript interactions (js: true when needed)
- Use data-testid attributes for stable selectors
- Include proper wait handling for async operations

Example structure:
```ruby
require 'rails_helper'

RSpec.describe 'Authentication', type: :system do
  describe 'sign up' do
    it 'allows a new user to create an account' do
      visit new_user_registration_path

      fill_in 'Email', with: 'newuser@example.com'
      fill_in 'Password', with: 'password123'
      fill_in 'Password confirmation', with: 'password123'
      click_button 'Sign up'

      expect(page).to have_content('Welcome!')
      expect(page).to have_current_path(dashboard_path)
    end

    it 'shows validation errors for invalid input' do
      visit new_user_registration_path

      fill_in 'Email', with: 'invalid'
      click_button 'Sign up'

      expect(page).to have_content('Email is invalid')
    end
  end

  describe 'sign in' do
    let!(:user) {{ create(:user, email: 'test@example.com', password: 'password123') }}

    it 'allows an existing user to sign in' do
      visit new_user_session_path

      fill_in 'Email', with: 'test@example.com'
      fill_in 'Password', with: 'password123'
      click_button 'Log in'

      expect(page).to have_current_path(dashboard_path)
      expect(page).to have_content('Signed in successfully')
    end
  end

  describe 'sign out' do
    let(:user) {{ create(:user) }}

    it 'allows a user to sign out' do
      sign_in user
      visit dashboard_path

      click_button 'Sign out'

      expect(page).to have_current_path(root_path)
      expect(page).to have_content('Signed out successfully')
    end
  end
end
```

{ctx.get_deduplication_instructions()}
"""

        try:
            result = llm.generate_json(TEST_AGENT_PROMPT, user_prompt)

            for f in result.get("files", []):
                path = f.get("path", "spec/system/system_spec.rb")
                content = f.get("content", "")
                ctx.add_file(path, content, f.get("language", "ruby"), "test")

        except Exception as e:
            self.logger.error(f"Failed to generate system specs: {e}")

    def _generate_factories(
        self, ctx: GenerationContext, spec, source_files: list
    ) -> None:
        """Generate FactoryBot factories."""
        # Build database table info
        tables_info = ""
        if spec and spec.database_schema:
            table_details = []
            for t in spec.database_schema:
                cols = [c.get("name", "?") for c in t.columns[:5]]
                table_details.append(f"- {t.name}: {', '.join(cols)}")
            tables_info = "\n".join(table_details)

        user_prompt = f"""Generate FactoryBot factories for Rails models.

## Database Tables/Models
{tables_info if tables_info else "See migrations/models for schema"}

## Source Files Structure
{ctx.get_folder_structure()}

## Requirements

Generate JSON with factory files:
{{
    "files": [
        {{
            "path": "spec/factories/users.rb",
            "language": "ruby",
            "content": "# FactoryBot factory",
            "exports": ["user", "admin_user"]
        }},
        {{
            "path": "spec/factories/posts.rb",
            "language": "ruby",
            "content": "# FactoryBot factory",
            "exports": ["post", "published_post"]
        }}
    ]
}}

Generate factories for each model:
1. spec/factories/users.rb - User factory with traits
2. spec/factories/[model].rb - For each database table

Each factory should:
- Use Faker for realistic test data
- Include common traits (e.g., :admin, :with_posts)
- Use sequences for unique attributes
- Define associations correctly
- Include transient attributes where useful

Example:
```ruby
FactoryBot.define do
  factory :user do
    sequence(:email) {{ |n| "user\#{{n}}@example.com" }}
    password {{ 'password123' }}
    first_name {{ Faker::Name.first_name }}
    last_name {{ Faker::Name.last_name }}

    trait :admin do
      role {{ 'admin' }}
    end

    trait :with_posts do
      transient do
        posts_count {{ 3 }}
      end

      after(:create) do |user, evaluator|
        create_list(:post, evaluator.posts_count, user: user)
      end
    end
  end
end
```
"""

        try:
            result = llm.generate_json(TEST_AGENT_PROMPT, user_prompt)

            for f in result.get("files", []):
                path = f.get("path", "spec/factories/factory.rb")
                content = f.get("content", "")
                exports = f.get("exports", [])
                if not exports:
                    exports = ctx.extract_exports_from_ruby(content)

                ctx.add_file(path, content, f.get("language", "ruby"), "factory", exports=exports)

        except Exception as e:
            self.logger.error(f"Failed to generate factories: {e}")

    def _push_tests_to_github(self, state: FactoryState, tests: list[GeneratedFile]):
        """Push test files to GitHub repository."""
        if not state.github_repo:
            self.logger.error("No GitHub repo info available - CodeAgent must run first")
            raise RuntimeError("No GitHub repo info available")

        repo_info = state.github_repo
        if not repo_info.get("owner") or not repo_info.get("name"):
            self.logger.error("GitHub repo info incomplete - missing owner or name")
            raise RuntimeError("GitHub repo info incomplete")

        try:
            file_data = [
                {"path": f.path, "content": f.content, "message": f"Add {f.path}"}
                for f in tests
            ]

            created = github.create_files_batch(
                repo_info["owner"],
                repo_info["name"],
                file_data
            )

            # Verify files were pushed
            if len(created) != len(tests):
                failed = [t.path for t in tests if t.path not in created]
                self.logger.warning(f"Failed to push {len(failed)} test files: {failed[:5]}")

            self.logger.info(f"Successfully pushed {len(created)} test files to GitHub")

        except Exception as e:
            self.logger.error(f"Failed to push tests to GitHub: {e}")
            raise RuntimeError(f"Failed to push tests to GitHub: {e}")
