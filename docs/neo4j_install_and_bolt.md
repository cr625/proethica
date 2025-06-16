# Installing Neo4j and Configuring Bolt Connector

This guide explains how to install Neo4j on Ubuntu Linux and ensure the Bolt connector is enabled for remote connections (default port 7687).

## 1. Install Neo4j

Add the official Neo4j repository and install Neo4j:

```bash
sudo apt-get update
sudo apt-get install -y wget apt-transport-https ca-certificates
wget -O - https://debian.neo4j.com/neotechnology.gpg.key | sudo apt-key add -
echo 'deb https://debian.neo4j.com stable 5' | sudo tee /etc/apt/sources.list.d/neo4j.list
sudo apt-get update
sudo apt-get install -y neo4j
```

## 2. Start and Enable Neo4j

```bash
sudo systemctl enable neo4j
sudo systemctl start neo4j
sudo systemctl status neo4j
```

## 3. Configure the Bolt Connector

Edit the Neo4j configuration file to ensure Bolt is enabled and listening on all interfaces:

```bash
sudo nano /etc/neo4j/neo4j.conf
```

Add or update the following line (remove duplicates):

```
dbms.connector.bolt.listen_address=0.0.0.0:7687
```

Save and exit, then restart Neo4j:

```bash
sudo systemctl restart neo4j
```

## 4. Verify Bolt is Listening

Check that Neo4j is listening on port 7687:

```bash
sudo netstat -tulnp | grep 7687
# or
sudo ss -tulnp | grep 7687
```

You should see output indicating that `java` (Neo4j) is listening on 0.0.0.0:7687.

## 5. Access Neo4j

- Bolt protocol: `bolt://localhost:7687` (for cypher-shell, drivers)
- Web browser: `http://localhost:7474`

## 6. Troubleshooting

- Ensure there is only one `dbms.connector.bolt.listen_address` line in the config.
- Restart Neo4j after any config changes.
- Check firewall settings if connecting remotely.

---

For more, see the [Neo4j Operations Manual](https://neo4j.com/docs/operations-manual/current/).
