import 'package:flutter/material.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'core/configures/firebase_options.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await Firebase.initializeApp(
    options: DefaultFirebaseOptions.currentPlatform,
  );
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'constructEYE',
      home: const FirestoreTestScreen(),
    );
  }
}

class FirestoreTestScreen extends StatefulWidget {
  const FirestoreTestScreen({super.key});

  @override
  State<FirestoreTestScreen> createState() => _FirestoreTestScreenState();
}

class _FirestoreTestScreenState extends State<FirestoreTestScreen> {
  final FirebaseFirestore _firestore = FirebaseFirestore.instance;
  String _status = 'Ready to test';
  bool _isLoading = false;

  Future<void> _addDataToFirestore() async {
    setState(() {
      _isLoading = true;
      _status = 'Adding data to Firestore...';
    });

    try {
      // Add data to Firestore
      await _firestore.collection('users').add({
        'name': 'mohamed yasser',
        'age': 21,
        'timestamp': FieldValue.serverTimestamp(),
      });

      setState(() {
        _isLoading = false;
        _status = 'Success! Data added to Firestore ✓';
      });
    } catch (e) {
      setState(() {
        _isLoading = false;
        _status = 'Error: $e';
      });
    }
  }

  Future<void> _readDataFromFirestore() async {
    setState(() {
      _isLoading = true;
      _status = 'Reading data from Firestore...';
    });

    try {
      // Read data from Firestore
      final QuerySnapshot querySnapshot = await _firestore.collection('users').get();

      if (querySnapshot.docs.isEmpty) {
        setState(() {
          _isLoading = false;
          _status = 'No data found in Firestore';
        });
      } else {
        String data = 'Data from Firestore:\n\n';
        for (var doc in querySnapshot.docs) {
          data += 'Name: ${doc['name']}\n';
          data += 'Age: ${doc['age']}\n';
          data += '---\n';
        }
        setState(() {
          _isLoading = false;
          _status = data;
        });
      }
    } catch (e) {
      setState(() {
        _isLoading = false;
        _status = 'Error: $e';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Firestore Test'),
        backgroundColor: Colors.blue,
      ),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(20.0),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Text(
                'Firebase Firestore Test',
                style: TextStyle(
                  fontSize: 24,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 40),
              if (_isLoading)
                const CircularProgressIndicator()
              else
                Text(
                  _status,
                  textAlign: TextAlign.center,
                  style: const TextStyle(fontSize: 16),
                ),
              const SizedBox(height: 40),
              ElevatedButton(
                onPressed: _isLoading ? null : _addDataToFirestore,
                style: ElevatedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(horizontal: 40, vertical: 15),
                ),
                child: const Text(
                  'Add Data to Firestore',
                  style: TextStyle(fontSize: 16),
                ),
              ),
              const SizedBox(height: 20),
              ElevatedButton(
                onPressed: _isLoading ? null : _readDataFromFirestore,
                style: ElevatedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(horizontal: 40, vertical: 15),
                ),
                child: const Text(
                  'Read Data from Firestore',
                  style: TextStyle(fontSize: 16),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}