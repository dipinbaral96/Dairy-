import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

void main() => runApp(const DairyCustomerApp());

class DairyCustomerApp extends StatefulWidget {
  const DairyCustomerApp({super.key});
  @override
  State<DairyCustomerApp> createState() => _DairyCustomerAppState();
}

class _DairyCustomerAppState extends State<DairyCustomerApp> {
  Locale _locale = const Locale('en');
  void setLanguage(String code) => setState(() => _locale = Locale(code));
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'Dairy Customer',
      locale: _locale,
      theme: ThemeData(colorSchemeSeed: const Color(0xff083a9e), useMaterial3: true),
      home: LoginScreen(onLanguage: setLanguage, language: _locale.languageCode),
    );
  }
}

class ApiService {
  // Android emulator: http://10.0.2.2:8000. Real phone: http://SERVER_IP:8000.
  static const String baseUrl = String.fromEnvironment('API_BASE_URL', defaultValue: 'http://10.0.2.2:8000');
  String? token;
  Future<void> loadToken() async => token = (await SharedPreferences.getInstance()).getString('token');
  Future<void> saveToken(String value) async { token = value; await (await SharedPreferences.getInstance()).setString('token', value); }
  Map<String, String> get headers => {'Authorization': 'Token ${token ?? ''}'};

  Future<Map<String, dynamic>> login(String username, String password) async {
    final response = await http.post(Uri.parse('$baseUrl/api/login/'), headers: {'Content-Type': 'application/json'}, body: jsonEncode({'username': username, 'password': password}));
    final data = jsonDecode(response.body) as Map<String, dynamic>;
    if (data['ok'] == true) await saveToken(data['token']);
    return data;
  }

  Future<List<dynamic>> products() async => (jsonDecode((await http.get(Uri.parse('$baseUrl/api/products/'), headers: headers)).body)['products'] ?? []) as List<dynamic>;
  Future<Map<String, dynamic>> profile() async => (jsonDecode((await http.get(Uri.parse('$baseUrl/api/customer/profile/'), headers: headers)).body)['profile'] ?? {}) as Map<String, dynamic>;
  Future<List<dynamic>> purchases() async => (jsonDecode((await http.get(Uri.parse('$baseUrl/api/customer/purchases/'), headers: headers)).body)['purchases'] ?? []) as List<dynamic>;
  Future<List<dynamic>> bills() async => (jsonDecode((await http.get(Uri.parse('$baseUrl/api/bills/'), headers: headers)).body)['bills'] ?? []) as List<dynamic>;
  Future<List<dynamic>> notifications() async => (jsonDecode((await http.get(Uri.parse('$baseUrl/api/notifications/'), headers: headers)).body)['notifications'] ?? []) as List<dynamic>;
}

final api = ApiService();

String t(String lang, String en, String ne) => lang == 'ne' ? ne : en;

class LoginScreen extends StatefulWidget {
  final void Function(String) onLanguage;
  final String language;
  const LoginScreen({super.key, required this.onLanguage, required this.language});
  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final username = TextEditingController(text: 'customer1');
  final password = TextEditingController(text: 'Customer@12345');
  String error = '';
  bool loading = false;
  @override
  Widget build(BuildContext context) {
    final lang = widget.language;
    return Scaffold(
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 420),
          child: Card(
            margin: const EdgeInsets.all(20),
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
                  Text(t(lang, 'Dairy Customer Login', 'डेरी ग्राहक लगइन'), style: Theme.of(context).textTheme.titleLarge),
                  DropdownButton<String>(value: lang, items: const [DropdownMenuItem(value: 'en', child: Text('EN')), DropdownMenuItem(value: 'ne', child: Text('ने'))], onChanged: (v) => widget.onLanguage(v ?? 'en')),
                ]),
                const SizedBox(height: 16),
                TextField(controller: username, decoration: InputDecoration(labelText: t(lang, 'Username / Mobile', 'प्रयोगकर्ता / मोबाइल'))),
                const SizedBox(height: 12),
                TextField(controller: password, obscureText: true, decoration: InputDecoration(labelText: t(lang, 'Password', 'पासवर्ड'))),
                if (error.isNotEmpty) Padding(padding: const EdgeInsets.only(top: 12), child: Text(error, style: const TextStyle(color: Colors.red))),
                const SizedBox(height: 16),
                FilledButton(onPressed: loading ? null : () async {
                  setState(() { loading = true; error = ''; });
                  final data = await api.login(username.text.trim(), password.text);
                  setState(() { loading = false; });
                  if (data['ok'] == true && mounted) {
                    Navigator.pushReplacement(context, MaterialPageRoute(builder: (_) => HomeScreen(language: lang, onLanguage: widget.onLanguage)));
                  } else {
                    setState(() => error = data['error']?.toString() ?? 'Login failed');
                  }
                }, child: Text(loading ? '...' : t(lang, 'Login', 'लगइन'))),
              ]),
            ),
          ),
        ),
      ),
    );
  }
}

class HomeScreen extends StatefulWidget {
  final String language;
  final void Function(String) onLanguage;
  const HomeScreen({super.key, required this.language, required this.onLanguage});
  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  int tab = 0;
  @override
  Widget build(BuildContext context) {
    final lang = widget.language;
    final pages = [
      AsyncList(title: t(lang, 'Products', 'उत्पादनहरू'), loader: api.products, fields: const ['name', 'code', 'available_stock', 'selling_price']),
      AsyncList(title: t(lang, 'Purchase History', 'खरिद इतिहास'), loader: api.purchases, fields: const ['date', 'bill_number', 'product', 'batch_number', 'quantity', 'amount', 'status']),
      AsyncList(title: t(lang, 'Bills', 'बिलहरू'), loader: api.bills, fields: const ['bill_number', 'date', 'total_amount', 'paid_amount', 'due_amount', 'status']),
      AsyncList(title: t(lang, 'Notifications', 'सूचनाहरू'), loader: api.notifications, fields: const ['title', 'message', 'status', 'created_at']),
      ProfilePage(language: lang),
    ];
    return Scaffold(
      appBar: AppBar(title: Text(t(lang, 'Dairy Customer', 'डेरी ग्राहक')), actions: [DropdownButton<String>(value: lang, items: const [DropdownMenuItem(value: 'en', child: Text('EN')), DropdownMenuItem(value: 'ne', child: Text('ने'))], onChanged: (v) => widget.onLanguage(v ?? 'en'))]),
      body: pages[tab],
      bottomNavigationBar: NavigationBar(selectedIndex: tab, onDestinationSelected: (i) => setState(() => tab = i), destinations: [
        NavigationDestination(icon: const Icon(Icons.inventory_2), label: t(lang, 'Products', 'उत्पादन')),
        NavigationDestination(icon: const Icon(Icons.history), label: t(lang, 'History', 'इतिहास')),
        NavigationDestination(icon: const Icon(Icons.receipt_long), label: t(lang, 'Bills', 'बिल')),
        NavigationDestination(icon: const Icon(Icons.notifications), label: t(lang, 'Notice', 'सूचना')),
        NavigationDestination(icon: const Icon(Icons.person), label: t(lang, 'Profile', 'प्रोफाइल')),
      ]),
    );
  }
}

class AsyncList extends StatelessWidget {
  final String title;
  final Future<List<dynamic>> Function() loader;
  final List<String> fields;
  const AsyncList({super.key, required this.title, required this.loader, required this.fields});
  @override
  Widget build(BuildContext context) {
    return FutureBuilder<List<dynamic>>(
      future: loader(),
      builder: (context, snap) {
        if (!snap.hasData) return const Center(child: CircularProgressIndicator());
        final rows = snap.data!;
        if (rows.isEmpty) return Center(child: Text('No records'));
        return ListView.builder(
          padding: const EdgeInsets.all(12),
          itemCount: rows.length,
          itemBuilder: (_, i) {
            final row = rows[i] as Map<String, dynamic>;
            return Card(child: ListTile(title: Text(row[fields.first]?.toString() ?? title), subtitle: Text(fields.skip(1).map((f) => '$f: ${row[f] ?? '-'}').join('\n'))));
          },
        );
      },
    );
  }
}

class ProfilePage extends StatelessWidget {
  final String language;
  const ProfilePage({super.key, required this.language});
  @override
  Widget build(BuildContext context) {
    return FutureBuilder<Map<String, dynamic>>(
      future: api.profile(),
      builder: (context, snap) {
        if (!snap.hasData) return const Center(child: CircularProgressIndicator());
        final p = snap.data!;
        return ListView(padding: const EdgeInsets.all(16), children: [
          Text(t(language, 'Profile', 'प्रोफाइल'), style: Theme.of(context).textTheme.headlineSmall),
          const SizedBox(height: 12),
          for (final entry in p.entries) Card(child: ListTile(title: Text(entry.key), subtitle: Text(entry.value?.toString() ?? '-'))),
        ]);
      },
    );
  }
}
