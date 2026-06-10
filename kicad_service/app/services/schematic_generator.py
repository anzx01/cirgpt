"""
KiCad Schematic Generator using SKiDL
"""
from skidl import *
from typing import Dict, Any, Optional
import os
import uuid
import tempfile
import logging

logger = logging.getLogger(__name__)

class KiCadSchematicGenerator:
    """Generate professional KiCad schematics from CircuitIR"""

    def __init__(self):
        """Initialize generator"""
        self.temp_dir = tempfile.gettempdir()

        # Set KiCad symbol library path
        symbol_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'symbols')
        symbol_dir = os.path.abspath(symbol_dir)

        if os.path.exists(symbol_dir):
            # Set environment variables
            os.environ['KICAD_SYMBOL_DIR'] = symbol_dir
            os.environ['KICAD8_SYMBOL_DIR'] = symbol_dir

            # Add to SKiDL search paths
            from skidl import lib_search_paths, KICAD
            if symbol_dir not in lib_search_paths[KICAD]:
                lib_search_paths[KICAD].append(symbol_dir)

            logger.info(f"✅ Using symbol library: {symbol_dir}")
            logger.info(f"✅ Added to lib_search_paths")
        else:
            logger.warning(f"⚠️ Symbol library not found at: {symbol_dir}")
            logger.warning("Please run: git clone https://gitlab.com/kicad/libraries/kicad-symbols.git symbols")

        logger.info("KiCad Schematic Generator initialized")

    def generate_from_circuit_ir(self, circuit_ir: Dict[str, Any]) -> Dict[str, str]:
        """
        Generate KiCad schematic from CircuitIR

        Args:
            circuit_ir: CircuitIR dictionary

        Returns:
            Dictionary with paths to generated files and SVG content
        """
        circuit_type = circuit_ir.get('circuit_type')

        logger.info(f"Generating schematic for circuit type: {circuit_type}")

        if circuit_type == 'opamp_inverting':
            return self._generate_opamp_inverting(circuit_ir)
        elif circuit_type == 'opamp_non_inverting':
            return self._generate_opamp_non_inverting(circuit_ir)
        elif circuit_type == '555_timer_blinker':
            return self._generate_555_timer(circuit_ir)
        elif circuit_type == 'led_current_limiter':
            return self._generate_led_circuit(circuit_ir)
        elif circuit_type == 'rc_low_pass_filter':
            return self._generate_rc_filter(circuit_ir)
        else:
            raise ValueError(f"Unsupported circuit type: {circuit_type}")

    def _generate_opamp_inverting(self, circuit_ir: Dict) -> Dict[str, str]:
        """Generate inverting op-amp schematic with SKiDL"""
        constraints = circuit_ir.get('constraints', {})
        gain = abs(constraints.get('gain', 10))
        supply = constraints.get('supply_voltage_v', 15)

        r_in = 10000  # 10k
        r_feedback = r_in * gain

        # Reset SKiDL for new circuit
        reset()

        # Set default tool to KiCad
        set_default_tool(KICAD)

        # Create nets
        gnd = Net('GND')
        vin_net = Net('IN')
        sum_net = Net('SUMMING')
        out_net = Net('OUTPUT')
        vcc_net = Net('VCC')
        vee_net = Net('VEE')

        # Power supply symbols - using proper KiCad 8 format
        try:
            from skidl import lib_search_paths, KICAD
            # Add symbol dir to search paths
            symbol_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'symbols')
            symbol_dir = os.path.abspath(symbol_dir)
            if symbol_dir not in lib_search_paths[KICAD]:
                lib_search_paths[KICAD].append(symbol_dir)
                logger.info(f"Added to lib_search_paths: {symbol_dir}")
        except:
            pass

        vcc_part = Part('power', '+15V', ref='#PWR01', dest=TEMPLATE)
        vcc_part[1] += vcc_net

        vee_part = Part('power', '-15V', ref='#PWR02', dest=TEMPLATE)
        vee_part[1] += vee_net

        # Input connector/test point
        vin_conn = Part('Connector', 'Conn_01x01', ref='J1', dest=TEMPLATE)
        vin_conn[1] += vin_net

        # Input resistor
        r1 = Part('Device', 'R', ref='R1')
        r1.value = f'{r_in}'
        r1.footprint = 'Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal'
        r1[1] += vin_net
        r1[2] += sum_net

        # Feedback resistor
        r2 = Part('Device', 'R', ref='R2')
        r2.value = f'{int(r_feedback)}'
        r2.footprint = 'Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal'
        r2[1] += out_net
        r2[2] += sum_net

        # Op-amp
        opamp = Part('Amplifier_Operational', 'LM741', ref='U1')
        opamp.footprint = 'Package_DIP:DIP-8_W7.62mm'
        opamp['-'] += sum_net  # Inverting input
        opamp['+'] += gnd      # Non-inverting input
        opamp['OUT'] += out_net
        opamp['V+'] += vcc_net
        opamp['V-'] += vee_net

        # Load resistor
        rload = Part('Device', 'R', ref='Rload')
        rload.value = '100k'
        rload.footprint = 'Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal'
        rload[1] += out_net
        rload[2] += gnd

        # Ground reference
        gnd_ref = Part('power', 'GND', ref='#PWR03')
        gnd_ref[1] += gnd

        # Generate files
        file_id = str(uuid.uuid4())[:8]
        base_name = f'opamp_inv_{file_id}'
        sch_file = os.path.join(self.temp_dir, f'{base_name}.kicad_sch')
        net_file = os.path.join(self.temp_dir, f'{base_name}.net')

        try:
            # Generate netlist
            generate_netlist(file_=net_file)

            # Generate schematic
            generate_schematic(file_=sch_file)

            logger.info(f"✅ Generated schematic: {sch_file}")

            # Read netlist for response
            with open(net_file, 'r') as f:
                netlist_content = f.read()

            return {
                'success': True,
                'schematic_path': sch_file,
                'netlist_path': net_file,
                'netlist': netlist_content,
                'message': 'Professional KiCad schematic generated'
            }

        except Exception as e:
            logger.error(f"Error generating schematic: {e}")
            raise

    def _generate_opamp_non_inverting(self, circuit_ir: Dict) -> Dict[str, str]:
        """Generate non-inverting op-amp schematic"""
        constraints = circuit_ir.get('constraints', {})
        gain = abs(constraints.get('gain', 10))
        supply = constraints.get('supply_voltage_v', 15)

        r1 = 10000  # Ground resistor
        r2 = r1 * (gain - 1)  # Feedback resistor for non-inverting

        reset()
        set_default_tool(KICAD)

        # Nets
        gnd = Net('GND')
        vin_net = Net('IN')
        sum_net = Net('SUMMING')
        out_net = Net('OUTPUT')
        vcc_net = Net('VCC')
        vee_net = Net('VEE')

        # Components
        vin = Part('Connector', 'Conn_01x01', ref='Vin')
        vin.value = 'SIN(0 0.1 1k)'
        vin[1] += vin_net
        vin[2] += gnd

        vcc = Part('power', 'VCC', ref='#PWR01')
        vcc[1] += vcc_net

        vee = Part('power', 'VEE', ref='#PWR02')
        vee[1] += vee_net

        r1_part = Part('Device', 'R', ref='R1')
        r1_part.value = f'{r1}'
        r1_part[1] += sum_net
        r1_part[2] += gnd

        r2_part = Part('Device', 'R', ref='R2')
        r2_part.value = f'{int(r2)}'
        r2_part[1] += out_net
        r2_part[2] += sum_net

        opamp = Part('Amplifier_Operational', 'LM741', ref='U1')
        opamp['+'] += vin_net  # Non-inverting input gets signal
        opamp['-'] += sum_net  # Inverting input for feedback
        opamp['OUT'] += out_net
        opamp['V+'] += vcc_net
        opamp['V-'] += vee_net

        rload = Part('Device', 'R', ref='Rload')
        rload.value = '100k'
        rload[1] += out_net
        rload[2] += gnd

        gnd_ref = Part('power', 'GND', ref='#PWR03')
        gnd_ref[1] += gnd

        # Generate
        file_id = str(uuid.uuid4())[:8]
        base_name = f'opamp_noninv_{file_id}'
        sch_file = os.path.join(self.temp_dir, f'{base_name}.kicad_sch')
        net_file = os.path.join(self.temp_dir, f'{base_name}.net')

        generate_netlist(file_=net_file)
        generate_schematic(file_=sch_file)

        with open(net_file, 'r') as f:
            netlist_content = f.read()

        return {
            'success': True,
            'schematic_path': sch_file,
            'netlist_path': net_file,
            'netlist': netlist_content,
            'message': 'Professional KiCad schematic generated'
        }

    def _generate_555_timer(self, circuit_ir: Dict) -> Dict[str, str]:
        """Generate 555 timer schematic"""
        constraints = circuit_ir.get('constraints', {})
        freq = constraints.get('target_frequency_hz', 1.0)
        supply = constraints.get('supply_voltage_v', 9.0)

        # Calculate timing components
        c1 = 10e-6  # 10uF
        r1 = 1000   # 1k
        r2 = (1.44 / (freq * c1) - r1) / 2
        r2 = max(100, min(r2, 1000000))

        reset()
        set_default_tool(KICAD)

        # Nets
        gnd = Net('GND')
        vcc_net = Net('VCC')
        out_net = Net('OUTPUT')
        thresh_net = Net('THRESHOLD')
        disch_net = Net('DISCHARGE')
        ctrl_net = Net('CONTROL')
        reset_net = Net('RESET')
        led_net = Net('LED')

        # Power
        vcc = Part('power', 'VCC', ref='#PWR01')
        vcc[1] += vcc_net

        # 555 Timer
        timer = Part('Timer', 'NE555', ref='U1')
        timer.footprint = 'Package_DIP:DIP-8_W7.62mm'
        timer['GND'] += gnd
        timer['TRIG'] += thresh_net
        timer['OUT'] += out_net
        timer['RESET'] += reset_net
        timer['CONT'] += ctrl_net
        timer['THRES'] += thresh_net
        timer['DISCH'] += disch_net
        timer['VCC'] += vcc_net

        # Timing resistors
        r1_part = Part('Device', 'R', ref='R1')
        r1_part.value = '1k'
        r1_part[1] += vcc_net
        r1_part[2] += disch_net

        r2_part = Part('Device', 'R', ref='R2')
        r2_part.value = f'{r2/1000:.1f}k'
        r2_part[1] += disch_net
        r2_part[2] += thresh_net

        # Timing capacitor
        c1_part = Part('Device', 'C', ref='C1')
        c1_part.value = '10uF'
        c1_part[1] += thresh_net
        c1_part[2] += gnd

        # Reset pull-up
        r_reset = Part('Device', 'R', ref='R_Reset')
        r_reset.value = '10k'
        r_reset[1] += vcc_net
        r_reset[2] += reset_net

        # Control bypass
        c_ctrl = Part('Device', 'C', ref='C_Ctrl')
        c_ctrl.value = '100nF'
        c_ctrl[1] += ctrl_net
        c_ctrl[2] += gnd

        # LED circuit
        r_led = Part('Device', 'R', ref='R_LED')
        r_led.value = '470'
        r_led[1] += out_net
        r_led[2] += led_net

        led = Part('Device', 'LED', ref='D1')
        led.footprint = 'LED_THT:LED_D5.0mm'
        led[1] += led_net  # Anode
        led[2] += gnd      # Cathode

        gnd_ref = Part('power', 'GND', ref='#PWR02')
        gnd_ref[1] += gnd

        # Generate
        file_id = str(uuid.uuid4())[:8]
        base_name = f'555_timer_{file_id}'
        sch_file = os.path.join(self.temp_dir, f'{base_name}.kicad_sch')
        net_file = os.path.join(self.temp_dir, f'{base_name}.net')

        generate_netlist(file_=net_file)
        generate_schematic(file_=sch_file)

        with open(net_file, 'r') as f:
            netlist_content = f.read()

        return {
            'success': True,
            'schematic_path': sch_file,
            'netlist_path': net_file,
            'netlist': netlist_content,
            'message': 'Professional 555 timer schematic generated'
        }

    def _generate_led_circuit(self, circuit_ir: Dict) -> Dict[str, str]:
        """Generate simple LED circuit"""
        constraints = circuit_ir.get('constraints', {})
        supply = constraints.get('supply_voltage_v', 5.0)
        current = constraints.get('target_current_a', 0.02)
        led_vf = 2.0

        resistor = (supply - led_vf) / current

        reset()
        set_default_tool(KICAD)

        gnd = Net('GND')
        vcc_net = Net('VCC')
        led_net = Net('LED')

        vcc = Part('power', 'VCC', ref='#PWR01')
        vcc[1] += vcc_net

        r1 = Part('Device', 'R', ref='R1')
        r1.value = f'{int(resistor)}'
        r1[1] += vcc_net
        r1[2] += led_net

        led = Part('Device', 'LED', ref='D1')
        led[1] += led_net
        led[2] += gnd

        gnd_ref = Part('power', 'GND', ref='#PWR02')
        gnd_ref[1] += gnd

        file_id = str(uuid.uuid4())[:8]
        base_name = f'led_circuit_{file_id}'
        sch_file = os.path.join(self.temp_dir, f'{base_name}.kicad_sch')
        net_file = os.path.join(self.temp_dir, f'{base_name}.net')

        generate_netlist(file_=net_file)
        generate_schematic(file_=sch_file)

        with open(net_file, 'r') as f:
            netlist_content = f.read()

        return {
            'success': True,
            'schematic_path': sch_file,
            'netlist_path': net_file,
            'netlist': netlist_content,
            'message': 'Professional LED circuit schematic generated'
        }

    def _generate_rc_filter(self, circuit_ir: Dict) -> Dict[str, str]:
        """Generate RC low-pass filter"""
        constraints = circuit_ir.get('constraints', {})
        resistance = constraints.get('resistance_ohm', 10000)
        capacitance = constraints.get('capacitance_f', 15.9e-9)

        reset()
        set_default_tool(KICAD)

        gnd = Net('GND')
        in_net = Net('IN')
        out_net = Net('OUT')

        vin = Part('Connector', 'Conn_01x01', ref='Vin')
        vin.value = 'AC 1 SIN(0 1 1000)'
        vin[1] += in_net
        vin[2] += gnd

        r1 = Part('Device', 'R', ref='R1')
        r1.value = f'{int(resistance)}'
        r1[1] += in_net
        r1[2] += out_net

        c1 = Part('Device', 'C', ref='C1')
        c1.value = f'{capacitance*1e9:.1f}n'
        c1[1] += out_net
        c1[2] += gnd

        gnd_ref = Part('power', 'GND', ref='#PWR01')
        gnd_ref[1] += gnd

        file_id = str(uuid.uuid4())[:8]
        base_name = f'rc_filter_{file_id}'
        sch_file = os.path.join(self.temp_dir, f'{base_name}.kicad_sch')
        net_file = os.path.join(self.temp_dir, f'{base_name}.net')

        generate_netlist(file_=net_file)
        generate_schematic(file_=sch_file)

        with open(net_file, 'r') as f:
            netlist_content = f.read()

        return {
            'success': True,
            'schematic_path': sch_file,
            'netlist_path': net_file,
            'netlist': netlist_content,
            'message': 'Professional RC filter schematic generated'
        }
