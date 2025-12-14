#!/usr/bin/env python3
"""
Interactive Development Script for Claude Code Integration.

This script enables interactive development with Claude in the terminal,
allowing real-time conversation and code modification for the trading bot.

Features:
- Loads all bot modules into the environment
- Maintains conversation history with Claude
- Streams real-time responses
- Special commands for common operations
- Ready for iterative development

Usage:
    python claude_interactive.py

Commands:
    quit, exit, q    - Exit the interactive session
    clear, cls       - Clear conversation history
    files            - List all bot files
    status           - Show bot status if running
    reload           - Reload all modules
    help, ?          - Show available commands

Author: AMT Trading Bot
Version: 1.0.0
"""

import os
import sys
import importlib
import readline
from datetime import datetime
from typing import Dict, List, Optional, Any

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# =============================================================================
# MODULE LOADER
# =============================================================================

class ModuleLoader:
    """Loads and manages trading bot modules."""

    MODULES = [
        'config',
        'market_structure',
        'order_flow',
        'correlation_analysis',
        'indicators',
        'risk_management',
        'strategy',
        'main',
    ]

    def __init__(self):
        """Initialize the module loader."""
        self.loaded_modules: Dict[str, Any] = {}
        self.load_all()

    def load_all(self) -> Dict[str, bool]:
        """
        Load all trading bot modules.

        Returns:
            Dictionary of module name -> load success.
        """
        results = {}
        for module_name in self.MODULES:
            try:
                if module_name in sys.modules:
                    # Reload if already loaded
                    self.loaded_modules[module_name] = importlib.reload(sys.modules[module_name])
                else:
                    self.loaded_modules[module_name] = importlib.import_module(module_name)
                results[module_name] = True
            except Exception as e:
                print(f"Error loading {module_name}: {e}")
                results[module_name] = False

        return results

    def reload_all(self) -> Dict[str, bool]:
        """
        Reload all modules.

        Returns:
            Dictionary of module name -> reload success.
        """
        return self.load_all()

    def get_module(self, name: str) -> Optional[Any]:
        """
        Get a loaded module by name.

        Args:
            name: Module name.

        Returns:
            Module or None if not loaded.
        """
        return self.loaded_modules.get(name)

    def list_modules(self) -> List[str]:
        """
        List all loaded modules.

        Returns:
            List of loaded module names.
        """
        return list(self.loaded_modules.keys())


# =============================================================================
# CONVERSATION MANAGER
# =============================================================================

class ConversationManager:
    """Manages conversation history for Claude interactions."""

    def __init__(self):
        """Initialize conversation manager."""
        self.history: List[Dict[str, str]] = []
        self.session_start = datetime.now()

    def add_message(self, role: str, content: str):
        """
        Add a message to history.

        Args:
            role: 'user' or 'assistant'.
            content: Message content.
        """
        self.history.append({
            'role': role,
            'content': content,
            'timestamp': datetime.now().isoformat(),
        })

    def get_history(self) -> List[Dict[str, str]]:
        """
        Get conversation history.

        Returns:
            List of message dictionaries.
        """
        return self.history

    def clear(self):
        """Clear conversation history."""
        self.history = []
        self.session_start = datetime.now()

    def get_context(self, max_messages: int = 20) -> str:
        """
        Get recent conversation context as a string.

        Args:
            max_messages: Maximum messages to include.

        Returns:
            Formatted conversation context.
        """
        recent = self.history[-max_messages:]
        context_parts = []
        for msg in recent:
            role = "User" if msg['role'] == 'user' else "Assistant"
            context_parts.append(f"{role}: {msg['content']}")
        return "\n\n".join(context_parts)


# =============================================================================
# INTERACTIVE SESSION
# =============================================================================

class InteractiveSession:
    """
    Interactive development session for the trading bot.

    This class provides an interactive environment for developing
    and testing the trading bot with Claude assistance.
    """

    COMMANDS = {
        'quit': 'Exit the session',
        'exit': 'Exit the session',
        'q': 'Exit the session',
        'clear': 'Clear conversation history',
        'cls': 'Clear conversation history',
        'files': 'List all bot files',
        'status': 'Show bot status',
        'reload': 'Reload all modules',
        'help': 'Show this help message',
        '?': 'Show this help message',
        'history': 'Show conversation history',
        'context': 'Show current context',
        'bot': 'Create/access bot instance',
        'analyze': 'Run quick analysis',
    }

    def __init__(self):
        """Initialize the interactive session."""
        self.module_loader = ModuleLoader()
        self.conversation = ConversationManager()
        self.bot_instance = None
        self.running = True

        # Setup readline for better input handling
        self._setup_readline()

    def _setup_readline(self):
        """Setup readline for command history."""
        histfile = os.path.expanduser('~/.claude_bot_history')
        try:
            readline.read_history_file(histfile)
            readline.set_history_length(1000)
        except FileNotFoundError:
            pass

        import atexit
        atexit.register(readline.write_history_file, histfile)

    def print_banner(self):
        """Print welcome banner."""
        print("\n" + "="*70)
        print("  AMT TRADING BOT - INTERACTIVE DEVELOPMENT SESSION")
        print("="*70)
        print(f"\n  Session started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  Python version: {sys.version.split()[0]}")
        print(f"  Working directory: {os.getcwd()}")
        print("\n  Loaded modules:")
        for module in self.module_loader.list_modules():
            print(f"    - {module}")
        print("\n  Type 'help' for available commands.")
        print("  Type your message to interact with Claude.")
        print("="*70 + "\n")

    def handle_command(self, command: str) -> bool:
        """
        Handle a special command.

        Args:
            command: Command string.

        Returns:
            True if command was handled.
        """
        cmd = command.lower().strip()

        if cmd in ('quit', 'exit', 'q'):
            self.running = False
            print("\nGoodbye! Session ended.")
            return True

        elif cmd in ('clear', 'cls'):
            self.conversation.clear()
            os.system('clear' if os.name == 'posix' else 'cls')
            print("Conversation history cleared.\n")
            return True

        elif cmd == 'files':
            self._show_files()
            return True

        elif cmd == 'status':
            self._show_status()
            return True

        elif cmd == 'reload':
            print("Reloading modules...")
            results = self.module_loader.reload_all()
            for name, success in results.items():
                status = "OK" if success else "FAILED"
                print(f"  {name}: {status}")
            print("Reload complete.\n")
            return True

        elif cmd in ('help', '?'):
            self._show_help()
            return True

        elif cmd == 'history':
            self._show_history()
            return True

        elif cmd == 'context':
            self._show_context()
            return True

        elif cmd == 'bot':
            self._create_bot()
            return True

        elif cmd == 'analyze':
            self._quick_analyze()
            return True

        return False

    def _show_files(self):
        """Show all bot files."""
        print("\nTrading Bot Files:")
        print("-" * 40)

        bot_dir = os.path.dirname(os.path.abspath(__file__))
        py_files = sorted([f for f in os.listdir(bot_dir) if f.endswith('.py')])
        md_files = sorted([f for f in os.listdir(bot_dir) if f.endswith('.md')])

        print("\nPython Files:")
        for f in py_files:
            path = os.path.join(bot_dir, f)
            size = os.path.getsize(path)
            print(f"  {f:<30} ({size:,} bytes)")

        if md_files:
            print("\nDocumentation:")
            for f in md_files:
                print(f"  {f}")

        print()

    def _show_status(self):
        """Show bot status."""
        print("\nBot Status:")
        print("-" * 40)

        if self.bot_instance:
            try:
                status = self.bot_instance.get_status()
                print(f"  Running: {status.get('is_running', False)}")
                print(f"  Symbol: {status.get('symbol', 'N/A')}")
                print(f"  Session: {status.get('session', 'N/A')}")
                if 'account' in status:
                    print(f"  Balance: ${status['account'].get('balance', 0):,.2f}")
                    print(f"  Equity: ${status['account'].get('equity', 0):,.2f}")
                print(f"  Positions: {status.get('positions', 0)}")
            except Exception as e:
                print(f"  Error getting status: {e}")
        else:
            print("  No bot instance created.")
            print("  Use 'bot' command to create one.")

        print()

    def _show_help(self):
        """Show help message."""
        print("\nAvailable Commands:")
        print("-" * 40)
        for cmd, desc in self.COMMANDS.items():
            print(f"  {cmd:<10} - {desc}")
        print("\nOr type any message to discuss with Claude.")
        print()

    def _show_history(self):
        """Show conversation history."""
        print("\nConversation History:")
        print("-" * 40)

        if not self.conversation.history:
            print("  No messages yet.")
        else:
            for i, msg in enumerate(self.conversation.history, 1):
                role = "You" if msg['role'] == 'user' else "Claude"
                content = msg['content'][:100] + "..." if len(msg['content']) > 100 else msg['content']
                print(f"  {i}. [{role}] {content}")

        print()

    def _show_context(self):
        """Show current context."""
        print("\nCurrent Context:")
        print("-" * 40)
        print(f"  Session start: {self.conversation.session_start}")
        print(f"  Messages: {len(self.conversation.history)}")
        print(f"  Modules loaded: {len(self.module_loader.loaded_modules)}")
        print(f"  Bot instance: {'Yes' if self.bot_instance else 'No'}")
        print()

    def _create_bot(self):
        """Create or show bot instance."""
        if self.bot_instance:
            print("\nBot instance already exists.")
            self._show_status()
        else:
            print("\nCreating bot instance...")
            try:
                main_module = self.module_loader.get_module('main')
                config_module = self.module_loader.get_module('config')

                if main_module and config_module:
                    config = config_module.get_default_config()
                    config.paper_trading = True
                    self.bot_instance = main_module.TradingBot(config)
                    print("Bot instance created successfully!")
                    self._show_status()
                else:
                    print("Error: Required modules not loaded.")
            except Exception as e:
                print(f"Error creating bot: {e}")

        print()

    def _quick_analyze(self):
        """Run a quick analysis."""
        print("\nRunning quick analysis...")

        if not self.bot_instance:
            self._create_bot()

        if self.bot_instance:
            try:
                main_module = self.module_loader.get_module('main')

                # Generate sample data
                candles = main_module.generate_sample_data(
                    symbol="SPY",
                    num_candles=50,
                    base_price=450.0,
                )

                # Process and analyze
                self.bot_instance.process_market_data(candles=candles)
                analysis = self.bot_instance.analyze()

                if analysis:
                    print(f"\nAnalysis Results:")
                    print(f"  Confluence: {analysis.confluence_score:.1f}")
                    print(f"  Strength: {analysis.signal_strength.name}")

                    if analysis.signal:
                        print(f"  Signal: {analysis.signal.signal_type.name}")
                        print(f"  Confidence: {analysis.signal.confidence:.1f}%")

                    print(f"\n  Notes:")
                    for note in analysis.notes[:5]:
                        print(f"    - {note}")
                else:
                    print("  No analysis results.")

            except Exception as e:
                print(f"Error during analysis: {e}")
                import traceback
                traceback.print_exc()

        print()

    def process_input(self, user_input: str):
        """
        Process user input.

        Args:
            user_input: User's input string.
        """
        stripped = user_input.strip()

        if not stripped:
            return

        # Check if it's a command
        if self.handle_command(stripped):
            return

        # Otherwise, treat as conversation
        self.conversation.add_message('user', stripped)

        # Generate response guidance
        print("\n" + "-"*40)
        print("To continue this conversation with Claude Code:")
        print("-"*40)
        print(f"\nYou said: {stripped[:200]}{'...' if len(stripped) > 200 else ''}")
        print("\nContext available:")
        print(f"  - {len(self.conversation.history)} messages in history")
        print(f"  - {len(self.module_loader.loaded_modules)} modules loaded")
        print(f"  - Bot instance: {'Active' if self.bot_instance else 'None'}")

        # Provide helpful suggestions based on input
        suggestions = self._get_suggestions(stripped)
        if suggestions:
            print("\nSuggested actions:")
            for s in suggestions:
                print(f"  - {s}")

        print("\n" + "-"*40 + "\n")

    def _get_suggestions(self, user_input: str) -> List[str]:
        """
        Get suggestions based on user input.

        Args:
            user_input: User's input string.

        Returns:
            List of suggestions.
        """
        suggestions = []
        lower_input = user_input.lower()

        if any(word in lower_input for word in ['analyze', 'analysis', 'test']):
            suggestions.append("Use 'analyze' command to run quick analysis")

        if any(word in lower_input for word in ['status', 'position', 'account']):
            suggestions.append("Use 'status' command to see current bot status")

        if any(word in lower_input for word in ['file', 'code', 'module']):
            suggestions.append("Use 'files' command to list all files")

        if any(word in lower_input for word in ['reload', 'refresh', 'update']):
            suggestions.append("Use 'reload' command to reload modules")

        if any(word in lower_input for word in ['help', 'command', 'how']):
            suggestions.append("Use 'help' command for available commands")

        return suggestions

    def run(self):
        """Run the interactive session."""
        self.print_banner()

        while self.running:
            try:
                user_input = input("You: ").strip()
                self.process_input(user_input)
            except KeyboardInterrupt:
                print("\n\nInterrupted. Type 'quit' to exit or continue typing.")
            except EOFError:
                self.running = False
                print("\nSession ended.")

        # Cleanup
        if self.bot_instance:
            try:
                self.bot_instance.stop()
            except:
                pass


# =============================================================================
# QUICK ACCESS FUNCTIONS
# =============================================================================

def get_bot():
    """
    Quick function to get a configured bot instance.

    Returns:
        TradingBot instance.
    """
    from main import TradingBot
    from config import get_default_config

    config = get_default_config()
    config.paper_trading = True
    return TradingBot(config)


def quick_analyze(num_candles: int = 50):
    """
    Run a quick analysis.

    Args:
        num_candles: Number of candles to generate.

    Returns:
        AnalysisResult.
    """
    from main import TradingBot, generate_sample_data
    from config import get_default_config

    config = get_default_config()
    config.paper_trading = True
    bot = TradingBot(config)

    candles = generate_sample_data(num_candles=num_candles)
    bot.process_market_data(candles=candles)

    return bot.analyze()


def load_all_modules():
    """
    Load all modules and return them as a dictionary.

    Returns:
        Dictionary of module name -> module.
    """
    loader = ModuleLoader()
    return loader.loaded_modules


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main():
    """Main entry point."""
    print("\nInitializing AMT Trading Bot Interactive Session...")

    try:
        session = InteractiveSession()
        session.run()
    except Exception as e:
        print(f"\nFatal error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
