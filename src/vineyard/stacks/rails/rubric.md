# Rails Build Rubric

## Project Setup
- `Gemfile` declares `rails ~> 7.1`, `pg`, `devise`, `stimulus-rails`, `turbo-rails`, `view_component`, `tailwindcss-rails`, `sidekiq`, `rspec-rails`
- `config/database.yml` is configured for PostgreSQL
- `config/routes.rb` declares routes for every feature in the spec
- `.env.example` lists every env var referenced in initializers

## Code Quality
- Strong parameters used in every controller
- ActiveRecord associations and validations match the database schema
- Service objects in `app/services/` handle business logic
- ViewComponents in `app/components/` cover reusable UI (button, card, modal, form fields)
- Stimulus controllers in `app/javascript/controllers/` drive interactivity
- Devise is configured with the right modules for the chosen auth flow

## Database
- Migrations exist for every model in `db/migrate/`
- Migration timestamps are unique and ordered correctly for foreign-key dependencies
- Indexes are declared on foreign keys and frequently queried columns

## Tests
- At least one model spec, one request spec, and one system spec exist under `spec/`
- `spec/rails_helper.rb` is configured

## Deliverables
- All output files live under `/mnt/session/outputs/`
- A `README.md` explains setup: install ruby, bundle, db:setup, run server
- Running `bundle install && bin/rails db:setup` would succeed
