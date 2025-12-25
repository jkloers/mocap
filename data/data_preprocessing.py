'''
This file is used to preprocess the motion data from the raw CSV file to a clean format.
The input format is a CSV file with the following columns:
- label
- accel
- gyro
- orientation
Those data are not in order, there are 60 (sometimes 61) samples for each movement.
We remove the 61th when it exists. In the raw csv, the data is ordered by the time
but for each movement we have first all of the samples for accelerometer, ax, ay, az, 
the all of the samples for gyroscope, gx, gy, gz, the all of the samples for orientation,
alpha, beta, gamma.

In the output file, we have the data ordered by the time for each movement, so we have
ax, ay, az, gx, gy, gz, alpha, beta, gamma for each time step in this order.

The output format is a CSV file with the following columns:
- label
- ax_1, ay_1, az_1, gx_1, gy_1, gz_1, alpha_1, beta_1, gamma_1, ...
- ax_60, ay_60, az_60, gx_60, gy_60, gz_60, alpha_60, beta_60, gamma_60
'''

import csv
import json
import os

def preprocess_dataset(input_file, output_file):
    """
    Preprocess motion data from raw CSV to clean format.
    
    Input format: CSV with columns including label, accel, gyro, orientation
    Output format: CSV with label and columns for each time step (1-60):
        ax_1, ay_1, az_1, gx_1, gy_1, gz_1, alpha_1, beta_1, gamma_1, ...
        ax_60, ay_60, az_60, gx_60, gy_60, gz_60, alpha_60, beta_60, gamma_60
    """
    
    # Generate column names
    columns = ['label']
    for step in range(1, 61):
        columns.extend([
            f'ax_{step}', f'ay_{step}', f'az_{step}',
            f'gx_{step}', f'gy_{step}', f'gz_{step}',
            f'alpha_{step}', f'beta_{step}', f'gamma_{step}'
        ])
    
    with open(input_file, 'r', encoding='utf-8') as infile, \
         open(output_file, 'w', encoding='utf-8', newline='') as outfile:
        
        reader = csv.DictReader(infile)
        writer = csv.DictWriter(outfile, fieldnames=columns)
        writer.writeheader()
        
        for row in reader:
            # Extract label
            label = row['label']
            
            # Parse JSON arrays
            accel_data = json.loads(row['accel'])
            gyro_data = json.loads(row['gyro'])
            orient_data = json.loads(row['orientation'])
            
            # Ensure we have exactly 60 samples (remove last if 61)
            accel_data = accel_data[:60]
            gyro_data = gyro_data[:60]
            orient_data = orient_data[:60]
            
            # Create output row
            output_row = {'label': label}
            
            # Extract data for each time step
            for step in range(60):
                step_num = step + 1
                
                # Extract acceleration data
                if step < len(accel_data):
                    output_row[f'ax_{step_num}'] = accel_data[step]['ax']
                    output_row[f'ay_{step_num}'] = accel_data[step]['ay']
                    output_row[f'az_{step_num}'] = accel_data[step]['az']
                else:
                    output_row[f'ax_{step_num}'] = ''
                    output_row[f'ay_{step_num}'] = ''
                    output_row[f'az_{step_num}'] = ''
                
                # Extract gyro data
                if step < len(gyro_data):
                    output_row[f'gx_{step_num}'] = gyro_data[step]['gx']
                    output_row[f'gy_{step_num}'] = gyro_data[step]['gy']
                    output_row[f'gz_{step_num}'] = gyro_data[step]['gz']
                else:
                    output_row[f'gx_{step_num}'] = ''
                    output_row[f'gy_{step_num}'] = ''
                    output_row[f'gz_{step_num}'] = ''
                
                # Extract orientation data
                if step < len(orient_data):
                    output_row[f'alpha_{step_num}'] = orient_data[step]['alpha']
                    output_row[f'beta_{step_num}'] = orient_data[step]['beta']
                    output_row[f'gamma_{step_num}'] = orient_data[step]['gamma']
                else:
                    output_row[f'alpha_{step_num}'] = ''
                    output_row[f'beta_{step_num}'] = ''
                    output_row[f'gamma_{step_num}'] = ''
            
            writer.writerow(output_row)
    
    print(f"Preprocessing complete! Output saved to {output_file}")


if __name__ == "__main__":
    # Default input and output file paths
    input_file = os.path.join(os.path.dirname(__file__), 'dataset1_3x40.csv')
    output_file = os.path.join(os.path.dirname(__file__), 'dataset1_3x40_clean.csv')
    
    preprocess_dataset(input_file, output_file)

