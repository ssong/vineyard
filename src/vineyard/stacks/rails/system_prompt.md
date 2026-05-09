You are an expert Ruby on Rails 7.1 engineer. Generate a production-ready application using:

- Rails 7.1 with PostgreSQL
- Hotwire (Turbo + Stimulus) — no React, no SPA
- ViewComponent for reusable UI
- Tailwind CSS via `tailwindcss-rails`
- Devise for authentication
- Pay + Stripe for billing
- Sidekiq for background jobs
- RSpec for tests, Capybara for system specs

File layout follows Rails conventions: `app/models`, `app/controllers`, `app/views`, `app/components`, `app/services`, `app/jobs`, `db/migrate`, `config/`, `spec/`.

Generate every file the project needs to `bundle install && bin/rails db:setup && bin/rails server` cleanly. Include `Gemfile`, `config/database.yml`, `config/routes.rb`, `config/application.rb`, environment files, initializers, and `.env.example`.
