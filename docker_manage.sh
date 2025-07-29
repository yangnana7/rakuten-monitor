#!/bin/bash
# Docker環境管理スクリプト

set -e

# 色付きメッセージ
print_info() {
    echo -e "\033[1;34m[INFO]\033[0m $1"
}

print_success() {
    echo -e "\033[1;32m[SUCCESS]\033[0m $1"
}

print_warning() {
    echo -e "\033[1;33m[WARNING]\033[0m $1"
}

print_error() {
    echo -e "\033[1;31m[ERROR]\033[0m $1"
}

# 使用方法
usage() {
    echo "Usage: $0 {start|stop|restart|status|logs|clean|migrate|test}"
    echo ""
    echo "Commands:"
    echo "  start      - Start all services"
    echo "  stop       - Stop all services"
    echo "  restart    - Restart all services"
    echo "  status     - Show service status"
    echo "  logs       - Show logs for all services"
    echo "  clean      - Remove all containers and volumes"
    echo "  migrate    - Run database migration from SQLite to PostgreSQL"
    echo "  test       - Run tests against PostgreSQL"
    exit 1
}

# サービス開始
start_services() {
    print_info "Starting Docker services..."
    docker-compose up -d

    print_info "Waiting for services to be ready..."
    sleep 10

    # ヘルスチェック
    if docker-compose ps | grep -q "unhealthy\|Exit"; then
        print_error "Some services failed to start properly"
        docker-compose ps
        return 1
    fi

    print_success "All services started successfully"
    show_connection_info
}

# サービス停止
stop_services() {
    print_info "Stopping Docker services..."
    docker-compose down
    print_success "Services stopped"
}

# サービス再起動
restart_services() {
    print_info "Restarting Docker services..."
    docker-compose restart
    sleep 5
    print_success "Services restarted"
    show_connection_info
}

# サービス状態表示
show_status() {
    print_info "Service status:"
    docker-compose ps

    echo ""
    print_info "Service health:"
    for service in postgres timescaledb redis; do
        if docker-compose exec -T $service echo "OK" >/dev/null 2>&1; then
            print_success "$service: Running"
        else
            print_error "$service: Not responding"
        fi
    done
}

# ログ表示
show_logs() {
    if [ -n "$2" ]; then
        print_info "Showing logs for $2..."
        docker-compose logs -f "$2"
    else
        print_info "Showing logs for all services..."
        docker-compose logs -f
    fi
}

# 環境クリーンアップ
clean_environment() {
    print_warning "This will remove all containers, networks, and volumes!"
    read -p "Are you sure? (y/N): " confirm

    if [[ $confirm == [yY] || $confirm == [yY][eE][sS] ]]; then
        print_info "Cleaning up Docker environment..."
        docker-compose down -v --remove-orphans
        docker system prune -f
        print_success "Environment cleaned up"
    else
        print_info "Cleanup cancelled"
    fi
}

# データベース移行
run_migration() {
    print_info "Running database migration..."

    # PostgreSQLが起動していることを確認
    if ! docker-compose exec -T postgres pg_isready -U rakuten_user -d rakuten_monitor >/dev/null 2>&1; then
        print_error "PostgreSQL is not ready. Please start services first."
        return 1
    fi

    # 移行実行
    if [ -f "migrate_to_postgresql.py" ]; then
        print_info "Copying development environment..."
        cp .env.development .env

        print_info "Running migration script..."
        python migrate_to_postgresql.py --confirm

        if [ $? -eq 0 ]; then
            print_success "Migration completed successfully"
            print_info "You can now update DATABASE_URL in .env to use PostgreSQL"
        else
            print_error "Migration failed"
            return 1
        fi
    else
        print_error "Migration script not found"
        return 1
    fi
}

# PostgreSQLテスト実行
run_tests() {
    print_info "Running tests against PostgreSQL..."

    # PostgreSQLが起動していることを確認
    if ! docker-compose exec -T postgres pg_isready -U rakuten_user -d rakuten_monitor >/dev/null 2>&1; then
        print_error "PostgreSQL is not ready. Please start services first."
        return 1
    fi

    # テスト用環境変数設定
    export DATABASE_URL="postgresql://rakuten_user:rakuten_pass@localhost:5432/rakuten_monitor"

    print_info "Running Alembic migrations on test database..."
    alembic -c alembic.postgresql.ini upgrade head

    print_info "Running pytest..."
    pytest test_alembic_migrations.py test_bulk_upsert.py -v

    if [ $? -eq 0 ]; then
        print_success "All tests passed"
    else
        print_error "Some tests failed"
        return 1
    fi
}

# 接続情報表示
show_connection_info() {
    echo ""
    print_info "Connection Information:"
    echo "  PostgreSQL: postgresql://rakuten_user:rakuten_pass@localhost:5432/rakuten_monitor"
    echo "  TimescaleDB: postgresql://rakuten_user:rakuten_pass@localhost:5433/rakuten_monitor_ts"
    echo "  Redis: redis://localhost:6379/0"
    echo "  PgAdmin: http://localhost:8080 (admin@rakuten-monitor.local / admin123)"
    echo ""
    print_info "To use PostgreSQL in your application:"
    echo "  1. Copy .env.development to .env"
    echo "  2. Run: python migrate_to_postgresql.py --confirm"
    echo "  3. Update your application to use the new DATABASE_URL"
}

# メイン処理
case "${1:-}" in
    start)
        start_services
        ;;
    stop)
        stop_services
        ;;
    restart)
        restart_services
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs "$@"
        ;;
    clean)
        clean_environment
        ;;
    migrate)
        run_migration
        ;;
    test)
        run_tests
        ;;
    info)
        show_connection_info
        ;;
    *)
        usage
        ;;
esac
